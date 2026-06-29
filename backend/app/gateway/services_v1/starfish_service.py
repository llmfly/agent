import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException, Request

from app.gateway.services_v1.data_source_service import (
    DataSourceRecord,
    _data_sources,
)

logger = logging.getLogger(__name__)


class StarfishService:
    def __init__(self) -> None:
        self.api_url_template = os.getenv(
            "STARFISH_API_URL",
            "http://172.16.0.247:8081/starfish/data-sources/{conversation_id}"
        )

    def _rewrite_url(self, url: str) -> str:
        if not url:
            return url
        import re
        from urllib.parse import urlparse, unquote, quote
        try:
            parsed_url = urlparse(url)
            # If it is a relative URL (no scheme)
            if not parsed_url.scheme:
                # Extract base URL from STARFISH_API_URL
                parsed_starfish = urlparse(self.api_url_template)
                if parsed_starfish.scheme and parsed_starfish.netloc:
                    base_url = f"{parsed_starfish.scheme}://{parsed_starfish.netloc}"
                else:
                    base_url = "http://172.16.0.160:25019"
                path_param = quote(url, safe='')
                rewritten_url = f"{base_url}/dip/common/file/download?path={path_param}"
                logger.info("Rewrote relative URL %s to %s", url, rewritten_url)
                return rewritten_url

            # Match MinIO console /browser/bucket_name/object_path pattern
            match = re.search(r'/browser/([^/]+)/(.+)', parsed_url.path)
            if match:
                bucket = unquote(match.group(1))
                object_path = unquote(match.group(2))
                
                # Extract base URL from STARFISH_API_URL
                parsed_starfish = urlparse(self.api_url_template)
                if parsed_starfish.scheme and parsed_starfish.netloc:
                    base_url = f"{parsed_starfish.scheme}://{parsed_starfish.netloc}"
                else:
                    host = parsed_url.hostname or "172.16.0.160"
                    base_url = f"http://{host}:25019"
                
                path_param = quote(f"{bucket}/{object_path}", safe='')
                rewritten_url = f"{base_url}/dip/common/file/download?path={path_param}"
                logger.info("Rewrote MinIO browser URL from %s to %s", url, rewritten_url)
                return rewritten_url
        except Exception as e:
            logger.warning("Error trying to rewrite url %s: %s", url, e)
        return url

    async def is_datasource_available(self, item: dict[str, Any]) -> bool:
        source_id = item.get("sourceId")
        source_type = item.get("sourceType")
        source_config = item.get("sourceConfig") or {}

        if source_type == "DATABASE":
            db_type = (source_config.get("databaseType") or "MYSQL").upper()
            if db_type == "MYSQL":
                host = source_config.get("host")
                port = int(source_config.get("port") or 3306)
                database = source_config.get("databaseName", "")
                username = source_config.get("username", "")
                password = source_config.get("password", "")

                if not host:
                    return False

                def _test_conn():
                    import pymysql
                    try:
                        conn = pymysql.connect(
                            host=host,
                            port=port,
                            user=username,
                            password=password,
                            database=database,
                            connect_timeout=3
                        )
                        conn.close()
                        return True
                    except Exception as e:
                        logger.warning("MySQL connection check failed for %s:%d/%s (ID: %s) - %s", host, port, database, source_id, e)
                        return False

                return await asyncio.to_thread(_test_conn)
            # Default to True for other database types
            return True

        elif source_type == "FILE":
            path = source_config.get("path")
            if path:
                # If it looks like a local file path, verify it exists
                if os.path.isabs(path) or os.path.exists(path):
                    return os.path.exists(path)
            return True

        return True

    async def fetch_and_sync_data_sources(self, conversation_id: str, request: Request) -> None:
        url = self.api_url_template.format(conversation_id=conversation_id)
        logger.info("Fetching starfish data sources from %s", url)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning(
                        "Starfish API returned status %d for conversation %s",
                        response.status_code,
                        conversation_id
                    )
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "code": "DATA_SOURCE_UNAVAILABLE",
                            "message": f"获取数据源信息失败，第三方服务返回状态码 {response.status_code}。"
                        }
                    )

                resp_json = response.json()
                if resp_json.get("code") != 200:
                    logger.warning(
                        "Starfish API response has code %s: %s",
                        resp_json.get("code"),
                        resp_json.get("msg")
                    )
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "code": "DATA_SOURCE_UNAVAILABLE",
                            "message": f"获取数据源信息失败：{resp_json.get('msg')}。"
                        }
                    )

                data_val = resp_json.get("data")
                if isinstance(data_val, list):
                    data_list = data_val
                elif isinstance(data_val, dict):
                    data_list = [data_val]
                else:
                    logger.warning("Starfish API data field is neither a list nor a dict: %s", type(data_val))
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "code": "DATA_SOURCE_UNAVAILABLE",
                            "message": "获取数据源数据格式不正确。"
                        }
                    )

                # Check availability of each data source concurrently
                async def _check_item(item):
                    is_avail = await self.is_datasource_available(item)
                    return item, is_avail

                if data_list:
                    tasks = [_check_item(item) for item in data_list]
                    checked_results = await asyncio.gather(*tasks)

                    valid_data_list = []
                    for item, is_avail in checked_results:
                        if is_avail:
                            valid_data_list.append(item)
                        else:
                            logger.warning("Skipping unavailable data source: ID %s, Name %s", item.get("sourceId"), item.get("sourceName"))

                    # If there were data sources returned but none of them are available, block request
                    if not valid_data_list:
                        raise HTTPException(
                            status_code=503,
                            detail={
                                "code": "DATA_SOURCE_UNAVAILABLE",
                                "message": "所有配置的数据源均不可用，请检查连接状态。"
                            }
                        )
                    data_list = valid_data_list

                await self.sync_data_sources(conversation_id, request, data_list)
        except httpx.TimeoutException as te:
            logger.warning("Timeout fetching starfish data sources for %s: %s", conversation_id, te)
            raise HTTPException(
                status_code=504,
                detail={
                    "code": "DATA_SOURCE_TIMEOUT",
                    "message": "获取数据源信息请求超时，请检查数据源服务状态。"
                }
            ) from te
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to fetch and sync starfish data sources for %s: %s", conversation_id, e)
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "DATA_SOURCE_UNAVAILABLE",
                    "message": f"数据源服务异常，无法获取配置信息：{str(e)}。"
                }
            ) from e

    async def sync_data_sources(self, conversation_id: str, request: Request, data_list: list[dict[str, Any]]) -> None:
        if not data_list:
            logger.info("sync_data_sources: data_list is empty, nothing to sync")
            return

        logger.info("=== sync_data_sources: conversation_id=%s, item_count=%d", conversation_id, len(data_list))

        # 1. Map starfish items to internal structures
        mapped_records: list[DataSourceRecord] = []

        for item in data_list:
            source_id = item.get("sourceId")
            source_type = item.get("sourceType")
            source_name = item.get("sourceName", "")
            source_config = item.get("sourceConfig") or {}

            if not source_id or not source_type:
                logger.warning("Missing sourceId or sourceType in starfish item: %s", item)
                continue

            if source_type == "DATABASE":
                db_type_raw = source_config.get("databaseType") or "MYSQL"
                db_type = db_type_raw.lower()
                host = source_config.get("host", "localhost")
                port = source_config.get("port", 3306)
                database = source_config.get("databaseName", "")
                username = source_config.get("username", "")
                password = source_config.get("password", "")

                content = f"[SQL] {db_type}://{host}:{port}/{database}"

                tables_raw = item.get("tables") or []
                tables = [t.get("tableName") for t in tables_raw if isinstance(t, dict) and t.get("tableName")]

                meta = {
                    "db_type": db_type,
                    "host": host,
                    "port": port,
                    "database": database,
                    "username": username,
                    "password": password,
                    "tables": tables,
                }
                internal_type = "sql"

            elif source_type == "FILE":
                url = source_config.get("url")
                path_val = source_config.get("path")
                
                # Preprocess and rewrite MinIO Console /browser/ URLs to direct download URLs
                rewritten_url = url
                if url:
                    rewritten_url = self._rewrite_url(url)
                
                # Extract filename
                file_name = source_config.get("fileName")
                if not file_name and rewritten_url:
                    from urllib.parse import urlparse, parse_qs, unquote
                    try:
                        parsed = urlparse(rewritten_url)
                        qs = parse_qs(parsed.query)
                        path_in_qs = qs.get("path")
                        if path_in_qs:
                            file_name = path_in_qs[0].split("/")[-1]
                        else:
                            file_name = parsed.path.split("/")[-1]
                        file_name = unquote(file_name)
                    except Exception as e:
                        logger.warning("Error parsing filename from URL %s: %s", rewritten_url, e)
                
                if not file_name:
                    file_name = path_val.split("/")[-1] if path_val else source_id

                # Default description fallback
                content = f"[File] {path_val or file_name}"

                # Try to load file content from URL first
                loaded = False
                if url:
                    # Validate URL has proper protocol before attempting download
                    if not rewritten_url.startswith(("http://", "https://")):
                        logger.warning("Skipping URL download: no http/https protocol in %s", rewritten_url)
                    else:
                        try:
                            logger.info("Attempting to load FILE source content from URL: %s", rewritten_url)
                            home_dir = os.getenv("DEER_FLOW_HOME")
                            if home_dir:
                                temp_dir = Path(home_dir) / "temp_downloads"
                            else:
                                from deerflow.config.paths import get_paths
                                temp_dir = get_paths().base_dir / "temp_downloads"
                            temp_dir.mkdir(parents=True, exist_ok=True)
                            temp_file_path = temp_dir / file_name

                            async with httpx.AsyncClient(timeout=15.0) as client:
                                file_resp = await client.get(rewritten_url)
                                if file_resp.status_code == 200:
                                    content_type = file_resp.headers.get("Content-Type", "").lower()
                                    if "text/html" in content_type:
                                        logger.info("URL returned HTML page. Extracting content via ReadabilityExtractor.")
                                        html_content = file_resp.text
                                        from deerflow.utils.readability import ReadabilityExtractor
                                        extractor = ReadabilityExtractor()
                                        article = extractor.extract_article(html_content)
                                        content = article.to_markdown()
                                        loaded = True
                                        logger.info("Successfully extracted HTML content to markdown: %d chars", len(content))
                                    else:
                                        temp_file_path.write_bytes(file_resp.content)
                                        logger.info("Downloaded FILE source from URL to %s", temp_file_path)
                                        from deerflow.utils.file_conversion import convert_file_to_markdown
                                        md_path = await convert_file_to_markdown(temp_file_path)
                                        if md_path and md_path.exists():
                                            content = md_path.read_text(encoding="utf-8")
                                            loaded = True
                                            logger.info("Successfully converted url file to markdown: %d chars", len(content))
                                else:
                                    logger.warning("Failed to download FILE from URL %s (status %d)", rewritten_url, file_resp.status_code)
                        except Exception as e:
                            logger.exception("Error downloading or converting file from URL: %s", e)

                # Fallback to local path if URL download was not performed or failed
                if not loaded and path_val:
                    try:
                        local_path = Path(path_val)
                        if not local_path.is_absolute():
                            project_root = os.getenv("DEER_FLOW_PROJECT_ROOT")
                            if project_root:
                                local_path = Path(project_root) / local_path

                        if local_path.exists() and local_path.is_file():
                            logger.info("Attempting to load FILE source content from local path: %s", local_path)
                            from deerflow.utils.file_conversion import convert_file_to_markdown
                            md_path = await convert_file_to_markdown(local_path)
                            if md_path and md_path.exists():
                                content = md_path.read_text(encoding="utf-8")
                                loaded = True
                                logger.info("Successfully converted local file to markdown: %d chars", len(content))
                        else:
                            logger.warning("Local file path does not exist or is not a file: %s", local_path)
                    except Exception as e:
                        logger.exception("Error reading or converting local file: %s", e)

                meta = dict(source_config)
                name_fallback = source_config.get("originalFilename") or source_config.get("fileName") or source_id
                source_name = source_name or name_fallback
                internal_type = "file"
            else:
                logger.warning("Unsupported starfish sourceType: %s", source_type)
                continue

            record = DataSourceRecord(
                datasource_id=source_id,
                conversation_id=conversation_id,
                type=internal_type,
                name=source_name,
                content=content,
                metadata=meta,
            )
            mapped_records.append(record)

        if not mapped_records:
            logger.info("sync_data_sources: no valid mapped records after parsing")
            return

        # 2. Sync to in-memory store
        if conversation_id not in _data_sources:
            _data_sources[conversation_id] = []
            logger.info("sync_data_sources: created new in-memory entry for conversation %s", conversation_id)

        # Avoid duplicate entries in in-memory store
        existing_ids = {r.datasource_id for r in _data_sources[conversation_id]}
        logger.info("sync_data_sources: existing_ids in memory = %s", existing_ids)
        for record in mapped_records:
            if record.datasource_id not in existing_ids:
                _data_sources[conversation_id].append(record)
                logger.info("sync_data_sources: appended record id=%s type=%s name=%s", record.datasource_id, record.type, record.name)
            else:
                # Update existing record in memory cache
                for i, r in enumerate(_data_sources[conversation_id]):
                    if r.datasource_id == record.datasource_id:
                        _data_sources[conversation_id][i] = record
                        logger.info("sync_data_sources: updated record id=%s type=%s name=%s", record.datasource_id, record.type, record.name)
                        break

        logger.info(
            "Successfully synchronized %d starfish data sources to in-memory store for conversation %s",
            len(mapped_records),
            conversation_id
        )
        logger.info("sync_data_sources: total in-memory records for %s = %d", conversation_id, len(_data_sources.get(conversation_id, [])))


# Singleton instance
starfish_service = StarfishService()

[1mdiff --git a/backend/app/gateway/services_v1/data_source_service.py b/backend/app/gateway/services_v1/data_source_service.py[m
[1mindex 3ddb2b8..43ed44a 100644[m
[1m--- a/backend/app/gateway/services_v1/data_source_service.py[m
[1m+++ b/backend/app/gateway/services_v1/data_source_service.py[m
[36m@@ -4,8 +4,8 @@[m [mSupports:[m
 - text: Direct text content[m
 - file: Uploaded file reference[m
 - url: URL reference[m
[31m-- sql: SQL database connection (supports NL-to-SQL query)[m
[31m-- es: Elasticsearch connection (supports NL-to-ES query)[m
[32m+[m[32m- sql: SQL database connection (enterprise Text-to-SQL pipeline)[m
[32m+[m[32m- es: Elasticsearch connection (Text-to-ES)[m
 """[m
 [m
 from __future__ import annotations[m
[36m@@ -44,7 +44,7 @@[m [mclass DataSourceRecord:[m
         self.conversation_id = conversation_id[m
         self.type = type[m
         self.name = name[m
[31m-        self.content = content  # For sql/es, this stores connection config summary[m
[32m+[m[32m        self.content = content[m
         self.status = status[m
         self.metadata = metadata or {}[m
         self.created_at = datetime.now(timezone.utc).isoformat()[m
[36m@@ -65,10 +65,8 @@[m [mclass DataSourceService:[m
         conversation_id: str,[m
         request: DataSourceCreateRequest,[m
     ) -> DataSourceResponse:[m
[31m-        """Register a new data source for a conversation."""[m
         datasource_id = f"ds_{uuid.uuid4().hex[:12]}"[m
 [m
[31m-        # Extract content based on type[m
         content = ""[m
         if request.type == "text":[m
             content = request.content or ""[m
[36m@@ -81,18 +79,12 @@[m [mclass DataSourceService:[m
             db_type = meta.get("db_type", "mysql")[m
             database = meta.get("database", "")[m
             host = meta.get("host", "localhost")[m
[31m-            content = ([m
[31m-                f"[SQL Database] type={db_type}, host={host}, "[m
[31m-                f"database={database}, table_schema={meta.get('table_schema', 'N/A')[:100]}"[m
[31m-            )[m
[32m+[m[32m            content = f"[SQL] {db_type}://{host}/{database}"[m
         elif request.type == "es":[m
             meta = request.metadata or {}[m
             hosts = meta.get("hosts", ["http://localhost:9200"])[m
             index = meta.get("index", "")[m
[31m-            content = ([m
[31m-                f"[Elasticsearch] hosts={hosts}, "[m
[31m-                f"index={index}, mapping={meta.get('index_mapping', 'N/A')[:100]}"[m
[31m-            )[m
[32m+[m[32m            content = f"[ES] {hosts}/{index}"[m
 [m
         record = DataSourceRecord([m
             datasource_id=datasource_id,[m
[36m@@ -107,23 +99,14 @@[m [mclass DataSourceService:[m
             _data_sources[conversation_id] = [][m
         _data_sources[conversation_id].append(record)[m
 [m
[31m-        logger.info([m
[31m-            "DataSource created: %s for conversation %s (type=%s, name=%s)",[m
[31m-            datasource_id,[m
[31m-            conversation_id,[m
[31m-            request.type,[m
[31m-            request.name,[m
[31m-        )[m
[31m-[m
[32m+[m[32m        logger.info("DataSource created: %s (type=%s, name=%s)", datasource_id, request.type, request.name)[m
         return self._record_to_response(record)[m
 [m
     async def list_datasources(self, conversation_id: str) -> list[DataSourceResponse]:[m
[31m-        """List all data sources for a conversation."""[m
         records = _data_sources.get(conversation_id, [])[m
         return [self._record_to_response(r) for r in records][m
 [m
     async def get_datasource(self, conversation_id: str, datasource_id: str) -> DataSourceResponse | None:[m
[31m-        """Get a specific data source by ID."""[m
         records = _data_sources.get(conversation_id, [])[m
         for r in records:[m
             if r.datasource_id == datasource_id:[m
[36m@@ -131,7 +114,6 @@[m [mclass DataSourceService:[m
         return None[m
 [m
     async def get_datasource_content(self, conversation_id: str, datasource_id: str) -> str | None:[m
[31m-        """Get the full content of a data source."""[m
         records = _data_sources.get(conversation_id, [])[m
         for r in records:[m
             if r.datasource_id == datasource_id:[m
[36m@@ -146,62 +128,50 @@[m [mclass DataSourceService:[m
     ) -> DataSourceQueryResponse:[m
         """Query a data source using natural language.[m
 [m
[31m-        For SQL/ES data sources, this performs NL-to-query conversion[m
[31m-        and execution. For text/file/url, it returns the stored content.[m
[32m+[m[32m        For SQL data sources, runs the full enterprise pipeline:[m
[32m+[m[32m        QueryRewriter → SchemaRetriever → EntityLinker → QueryPlanner[m
[32m+[m[32m        → FewShotRetrieval → ContextBuilder → LLM → SQLGlotValidator[m
[32m+[m[32m        → CostEstimator → Optimizer → Repairer(retry) → Executor[m
[32m+[m
[32m+[m[32m        For ES data sources: NL → ES DSL → execute.[m
[32m+[m[32m        For text/file/url: returns stored content.[m
         """[m
         records = _data_sources.get(conversation_id, [])[m
         record = next((r for r in records if r.datasource_id == datasource_id), None)[m
 [m
         if record is None:[m
             return DataSourceQueryResponse([m
[31m-                datasource_id=datasource_id,[m
[31m-                query=query_request.query,[m
[31m-                generated_query="",[m
[31m-                error=f"DataSource {datasource_id} not found",[m
[32m+[m[32m                datasource_id=datasource_id, query=query_request.query,[m
[32m+[m[32m                generated_query="", error=f"DataSource {datasource_id} not found",[m
             )[m
 [m
         if record.type == "sql":[m
             result = await self._nl_engine.query_sql([m
[31m-                query_request.query,[m
[31m-                record.metadata,[m
[31m-                max_results=query_request.max_results,[m
[32m+[m[32m                query_request.query, record.metadata, max_results=query_request.max_results,[m
             )[m
             return DataSourceQueryResponse([m
[31m-                datasource_id=datasource_id,[m
[31m-                query=query_request.query,[m
[32m+[m[32m                datasource_id=datasource_id, query=query_request.query,[m
                 generated_query=result.get("generated_query", ""),[m
[31m-                columns=result.get("columns", []),[m
[31m-                rows=result.get("rows", []),[m
[31m-                row_count=result.get("row_count", 0),[m
[31m-                error=result.get("error"),[m
[32m+[m[32m                columns=result.get("columns", []), rows=result.get("rows", []),[m
[32m+[m[32m                row_count=result.get("row_count", 0), error=result.get("error"),[m
             )[m
 [m
         elif record.type == "es":[m
             result = await self._nl_engine.query_es([m
[31m-                query_request.query,[m
[31m-                record.metadata,[m
[31m-                max_results=query_request.max_results,[m
[32m+[m[32m                query_request.query, record.metadata, max_results=query_request.max_results,[m
             )[m
             return DataSourceQueryResponse([m
[31m-                datasource_id=datasource_id,[m
[31m-                query=query_request.query,[m
[32m+[m[32m                datasource_id=datasource_id, query=query_request.query,[m
                 generated_query=result.get("generated_query", ""),[m
[31m-                columns=result.get("columns", []),[m
[31m-                rows=result.get("rows", []),[m
[31m-                row_count=result.get("row_count", 0),[m
[31m-                error=result.get("error"),[m
[32m+[m[32m                columns=result.get("columns", []), rows=result.get("rows", []),[m
[32m+[m[32m                row_count=result.get("row_count", 0), error=result.get("error"),[m
        
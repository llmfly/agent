"use client";

export function HeroSection() {
  const handleCTA = () => {
    window.location.href = "/workspace";
  };

  return (
    <section className="hero-section">
      <div className="hero-layout">
        <div className="hero-content reveal-up">
          <h1 className="title">让智能体可构建、可编排、可推理</h1>
          <p className="subtitle">本体智能，让智能体可构建、可编排、可推理</p>
          <div className="hero-actions">
            <button type="button" className="cta-primary" onClick={handleCTA}>
              开始体验
            </button>
          </div>
        </div>
        <div className="insight-panel">
          <div className="stat-card" style={{ "--card-stagger": 0 } as React.CSSProperties}>
            <div className="stat-headline">
              <span className="stat-icon">
                <DatabaseIcon />
              </span>
              <span className="card-tag tag-purple">RAG + 图谱</span>
            </div>
            <p className="stat-label">知识库管理</p>
            <p className="stat-description">融合检索增强生成与知识图谱技术</p>
          </div>
          <div className="stat-card" style={{ "--card-stagger": 1 } as React.CSSProperties}>
            <div className="stat-headline">
              <span className="stat-icon">
                <WorkflowIcon />
              </span>
              <span className="card-tag tag-cyan">LangGraph</span>
            </div>
            <p className="stat-label">智能体编排</p>
            <p className="stat-description">基于 LangGraph 的多智能体协作框架</p>
          </div>
          <div className="stat-card" style={{ "--card-stagger": 2 } as React.CSSProperties}>
            <div className="stat-headline">
              <span className="stat-icon">
                <ScanEyeIcon />
              </span>
              <span className="card-tag tag-blue">OCR + VL</span>
            </div>
            <p className="stat-label">多模态解析</p>
            <p className="stat-description">支持 PDF、图片、表格等多种格式解析</p>
          </div>
          <div className="stat-card" style={{ "--card-stagger": 3 } as React.CSSProperties}>
            <div className="stat-headline">
              <span className="stat-icon">
                <ContainerIcon />
              </span>
              <span className="card-tag tag-green">Docker</span>
            </div>
            <p className="stat-label">私有化部署</p>
            <p className="stat-description">完全本地部署，数据安全可控</p>
          </div>
        </div>
      </div>
    </section>
  );
}

function DatabaseIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
      <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3" />
    </svg>
  );
}

function WorkflowIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="7" height="7" x="3" y="3" rx="1" />
      <rect width="7" height="7" x="14" y="3" rx="1" />
      <rect width="7" height="7" x="14" y="14" rx="1" />
      <rect width="7" height="7" x="3" y="14" rx="1" />
      <path d="M10 6.5h4" />
      <path d="M17 10v4" />
      <path d="M14 17.5h-4" />
    </svg>
  );
}

function ScanEyeIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7V5a2 2 0 0 1 2-2h2" />
      <path d="M17 3h2a2 2 0 0 1 2 2v2" />
      <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
      <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
      <circle cx="12" cy="12" r="3" />
      <path d="M12 9v1" />
      <path d="M12 14v1" />
    </svg>
  );
}

function ContainerIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 7.92v8.16a1.5 1.5 0 0 1-.75 1.3l-8.5 4.92a1.5 1.5 0 0 1-1.5 0l-8.5-4.92a1.5 1.5 0 0 1-.75-1.3V7.92a1.5 1.5 0 0 1 .75-1.3l8.5-4.92a1.5 1.5 0 0 1 1.5 0l8.5 4.92a1.5 1.5 0 0 1 .75 1.3Z" />
      <path d="M12 2.7v8.62" />
      <path d="m3 7 9 5.2 9-5.2" />
    </svg>
  );
}

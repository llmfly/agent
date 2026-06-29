export function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="site-footer">
      <div className="footer-content">
        <p className="copyright">© 数据空间研究院 {year} v0.1.0</p>
      </div>
    </footer>
  );
}

/* Header Navigation Component */
(function() {
  const headerHTML = `
    <header class="site-header">
      <div class="wrap header-wrap">
        <a class="brand" href="./index.html" aria-label="Sophia Code home">
          <span class="brand-mark" aria-hidden="true"><i class="bi bi-lightbulb"></i></span>
          <span class="brand-text">Sophia Code</span>
        </a>
        <nav class="nav" aria-label="Primary">
          <a class="nav-link" href="./index.html">Home</a>
          <a class="nav-link" href="./product.html">Product</a>
          <a class="nav-link" href="./gallery.html">Gallery</a>
          <a class="nav-link" href="./setup.html">Setup</a>
          <a class="nav-link" href="./demo.html">Demo</a>
        </nav>
        <div class="nav-cta">
          <a class="btn btn-ghost portfolio-btn" href="https://alexbio.onrender.com/" target="_blank" rel="noopener" aria-label="Portfolio" title="Explore other projects">
            <i class="bi bi-briefcase"></i>
          </a>
          <a class="btn btn-ghost" href="https://github.com/AlexBiobelemo/Sophia-Code" target="_blank" rel="noopener" aria-label="GitHub">
            <i class="bi bi-github"></i>
          </a>
          <a class="btn btn-primary" href="https://sophia-code-wwhm.onrender.com" target="_blank" rel="noopener">
            <i class="bi bi-box-arrow-up-right"></i>
            Live demo
          </a>
        </div>
        <button class="menu-btn" type="button" aria-label="Open menu" aria-expanded="false">
          <i class="bi bi-list"></i>
        </button>
      </div>
      <div class="mobile-menu" hidden>
        <div class="wrap mobile-menu-wrap">
          <a class="nav-link" href="./index.html">Home</a>
          <a class="nav-link" href="./product.html">Product</a>
          <a class="nav-link" href="./gallery.html">Gallery</a>
          <a class="nav-link" href="./setup.html">Setup</a>
          <a class="nav-link" href="./demo.html">Demo</a>
          <a class="nav-link" href="https://alexbio.onrender.com/" target="_blank" rel="noopener">Portfolio</a>
          <a class="nav-link" href="https://sophia-code-wwhm.onrender.com" target="_blank" rel="noopener">Live demo</a>
        </div>
      </div>
    </header>
  `;

  const footerHTML = `
    <footer class="footer">
      <div class="wrap footer-wrap">
        <div class="footer-left">
          <div class="brand brand-footer">
            <span class="brand-mark" aria-hidden="true"><i class="bi bi-lightbulb"></i></span>
            <span class="brand-text">Sophia Code</span>
          </div>
          <p class="fine">Built by Alex Alagoa Biobelemo.</p>
        </div>
        <div class="footer-right" aria-label="Developer links">
          <a class="icon-link" href="mailto:alexbio0405@gmail.com" aria-label="Email"><i class="bi bi-envelope"></i></a>
          <a class="icon-link" href="https://www.linkedin.com/in/alex-alagoa-biobelemo/" target="_blank" rel="noopener" aria-label="LinkedIn"><i class="bi bi-linkedin"></i></a>
          <a class="icon-link" href="https://github.com/AlexBiobelemo" target="_blank" rel="noopener" aria-label="GitHub"><i class="bi bi-github"></i></a>
          <a class="icon-link" href="https://x.com/AlexarGreatest" target="_blank" rel="noopener" aria-label="X"><i class="bi bi-twitter-x"></i></a>
        </div>
      </div>
    </footer>
  `;

  function updateActiveNav(page) {
    document.querySelectorAll('.nav-link').forEach(link => {
      const href = link.getAttribute('href');
      link.classList.remove('is-active');

      if (href && (href.startsWith('http') || href.startsWith('https'))) {
        return;
      }

      if (href === page || href === './' + page) {
        link.classList.add('is-active');
      }
    });

    if (page === 'index.html' || page === '') {
      const homeLink = document.querySelector('.nav-link[href="./index.html"]');
      if (homeLink) {
        homeLink.classList.add('is-active');
      }
    }
  }

  function loadComponents() {
    const headerPlaceholder = document.getElementById('site-header');
    const footerPlaceholder = document.getElementById('site-footer');

    let currentPage = window.location.pathname.split('/').pop() || 'index.html';

    if (headerPlaceholder) {
      headerPlaceholder.innerHTML = headerHTML;
      updateActiveNav(currentPage);

      const btn = document.querySelector('.menu-btn');
      const menu = document.querySelector('.mobile-menu');
      if (btn && menu) {
        const setOpen = (open) => {
          btn.setAttribute('aria-expanded', open ? 'true' : 'false');
          if (open) menu.removeAttribute('hidden');
          else menu.setAttribute('hidden', '');
        };
        setOpen(false);
        btn.addEventListener('click', () => {
          const open = btn.getAttribute('aria-expanded') === 'true';
          setOpen(!open);
        });
      }
    }

    if (footerPlaceholder) {
      footerPlaceholder.innerHTML = footerHTML;
    }
  }

  loadComponents();

  window.loadSiteComponents = loadComponents;
})();

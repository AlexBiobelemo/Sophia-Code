(() => {
  const prefersReduced =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function qs(sel, root = document) {
    return root.querySelector(sel);
  }

  function qsa(sel, root = document) {
    return Array.from(root.querySelectorAll(sel));
  }

  function initMobileMenu() {
    const btn = qs(".menu-btn");
    const menu = qs(".mobile-menu");
    if (!btn || !menu) return;

    const setOpen = (open) => {
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) menu.removeAttribute("hidden");
      else menu.setAttribute("hidden", "");
    };

    setOpen(false);
    btn.addEventListener("click", () => {
      const open = btn.getAttribute("aria-expanded") === "true";
      setOpen(!open);
    });
  }

  function updateActiveNav() {
    const path = (window.location.pathname.split("/").pop() || "index.html").toLowerCase();
    qsa(".nav-link").forEach((a) => a.classList.remove("is-active"));
    const match = qsa(".nav-link").find((a) => (a.getAttribute("href") || "").toLowerCase().endsWith(path));
    if (match) match.classList.add("is-active");
  }

  function initMascotEyes() {
    const pupils = qsa(".mascot .pupil");
    const head = qs(".mascot-head");
    if (!pupils.length || !head) return;

    const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

    window.addEventListener("mousemove", (e) => {
      const r = head.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      const mag = Math.max(1, Math.hypot(dx, dy));
      const nx = dx / mag;
      const ny = dy / mag;
      const px = clamp(nx * 5.0, -5, 5);
      const py = clamp(ny * 4.0, -4, 4);
      pupils.forEach((p) => {
        p.style.transform = `translate(${px}px, ${py}px)`;
      });
    });
  }

  function initSmoothScroll() {
    if (prefersReduced) return null;
    if (!window.Lenis) return null;

    const lenis = new window.Lenis({
      duration: 1.15,
      smoothWheel: true,
      smoothTouch: false,
      wheelMultiplier: 0.85,
    });

    function raf(time) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);
    return lenis;
  }

  function initGsapBase() {
    if (prefersReduced) return;
    if (!window.gsap) return;

    try {
      if (window.ScrollTrigger) window.gsap.registerPlugin(window.ScrollTrigger);
    } catch (_) {}

    // Entrance
    const hero = qs(".hero-wrap") || qs(".page-hero-wrap");
    if (hero) {
      const els = qsa(".kicker, .hero-title, .hero-sub, .hero-actions, .hero-metrics, .page-title, .page-sub", hero);
      window.gsap.fromTo(
        els,
        { y: 18, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.7, ease: "power3.out", stagger: 0.06, delay: 0.05 }
      );
    }

    // Parallax shots
    if (window.ScrollTrigger) {
      qsa("[data-parallax]").forEach((el) => {
        const amt = Number(el.getAttribute("data-parallax") || "0.1");
        window.gsap.to(el, {
          y: () => Math.round(window.innerHeight * amt),
          ease: "none",
          scrollTrigger: {
            trigger: el,
            start: "top bottom",
            end: "bottom top",
            scrub: true,
          },
        });
      });
    }

    // Marquee
    const track = qs(".marquee-track");
    if (track && !prefersReduced) {
      window.gsap.to(track, { xPercent: -50, ease: "none", duration: 22, repeat: -1 });
    }
  }

  function initBarba(lenis) {
    if (!window.barba || prefersReduced) return;
    if (!window.gsap) return;

    let overlay = qs(".barba-overlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.className = "barba-overlay";
      document.body.appendChild(overlay);
    }

    function scrollTopFast() {
      try {
        if (lenis) lenis.scrollTo(0, { immediate: true });
      } catch (_) {}
      window.scrollTo(0, 0);
    }

    window.barba.init({
      preventRunning: true,
      transitions: [
        {
          name: "fade-swipe",
          async leave(data) {
            await window.gsap.to(overlay, { opacity: 1, duration: 0.18, ease: "power2.out" });
            await window.gsap.to(data.current.container, { opacity: 0.15, duration: 0.12, ease: "power2.out" });
          },
          async enter(data) {
            scrollTopFast();
            data.next.container.style.opacity = "0";
            await window.gsap.to(data.next.container, { opacity: 1, duration: 0.18, ease: "power2.out" });
            await window.gsap.to(overlay, { opacity: 0, duration: 0.22, ease: "power2.out" });
          },
        },
      ],
      views: [
        {
          namespace: "home",
          afterEnter() {
            initMascotEyes();
          },
        },
      ],
    });

    try {
      window.barba.hooks.afterEnter(() => {
        updateActiveNav();
        initGsapBase();
      });
    } catch (_) {}
  }

  function initAll() {
    initMobileMenu();
    updateActiveNav();
    const lenis = initSmoothScroll();
    initGsapBase();
    initMascotEyes();
    initBarba(lenis);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();

(() => {
  const prefersReduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

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

  function initSmoothScroll() {
    if (prefersReduced) return null;
    if (!window.Lenis) return null;

    const lenis = new window.Lenis({
      duration: 1.0,
      smoothWheel: true,
      smoothTouch: false,
      wheelMultiplier: 0.9,
      touchMultiplier: 2,
      infinite: false,
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

    const hero = qs(".hero-wrap") || qs(".page-hero-wrap");
    if (hero) {
      const elements = qsa(".kicker, .hero-title, .hero-sub, .hero-actions, .hero-features, .page-title, .page-sub", hero);
      if (elements.length) {
        window.gsap.fromTo(
          elements,
          { y: 30, opacity: 0 },
          {
            y: 0,
            opacity: 1,
            duration: 0.6,
            ease: "power2.out",
            stagger: 0.08,
            delay: 0.1,
          }
        );
      }
    }

    if (window.ScrollTrigger) {
      qsa(".section-head").forEach((el) => {
        window.gsap.fromTo(
          el,
          { y: 30, opacity: 0 },
          {
            y: 0,
            opacity: 1,
            duration: 0.7,
            ease: "power2.out",
            scrollTrigger: {
              trigger: el,
              start: "top 85%",
              once: true,
            },
          }
        );
      });

      qsa(".grid-3, .grid-2").forEach((grid) => {
        const cards = qsa(".card", grid);
        if (cards.length) {
          window.gsap.fromTo(
            cards,
            { y: 40, opacity: 0, scale: 0.96 },
            {
              y: 0,
              opacity: 1,
              scale: 1,
              duration: 0.6,
              ease: "power2.out",
              stagger: 0.06,
              scrollTrigger: {
                trigger: grid,
                start: "top 85%",
                once: true,
              },
            }
          );
        }
      });

      const ctaWrap = qs(".cta-wrap");
      if (ctaWrap) {
        window.gsap.to(ctaWrap, {
          boxShadow: "0 0 50px rgba(30, 91, 184, 0.12)",
          duration: 4,
          repeat: -1,
          yoyo: true,
          ease: "sine.inOut",
          scrollTrigger: {
            trigger: ctaWrap,
            start: "top 80%",
          },
        });
      }

      qsa(".feature-pill").forEach((pill, i) => {
        window.gsap.to(pill, {
          y: -5,
          duration: 2.5 + (i * 0.15),
          repeat: -1,
          yoyo: true,
          ease: "sine.inOut",
          delay: i * 0.08,
        });
      });
    }

    // Marquee animation - infinite smooth scroll
    const track = qs(".marquee-track");
    if (track && !prefersReduced) {
      // Clone content for seamless infinite loop
      const content = track.innerHTML;
      track.innerHTML = content + content;
      
      window.gsap.to(track, {
        xPercent: -50,
        ease: "none",
        duration: 40,
        repeat: -1,
      });
    }

    qsa(".card h3 i").forEach((icon) => {
      window.gsap.to(icon, {
        rotation: 8,
        scale: 1.08,
        duration: 2.5,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
        scrollTrigger: {
          trigger: icon,
          start: "top 90%",
        },
      });
    });
  }

  function initAll() {
    initMobileMenu();
    updateActiveNav();
    initGsapBase();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();

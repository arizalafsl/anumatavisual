/* =========================
   NAVBAR
========================= */

const navbar = document.getElementById("navbar");
const menuToggle = document.getElementById("menuToggle");
const navLinks = document.getElementById("navLinks");

window.addEventListener("scroll", () => {
  navbar.classList.toggle("scrolled", window.scrollY > 30);
});

menuToggle.addEventListener("click", () => {
  const open = navLinks.classList.toggle("open");

  menuToggle.setAttribute(
    "aria-expanded",
    open
  );
});

document.querySelectorAll(".nav-links a").forEach(link => {
  link.addEventListener("click", () => {
    navLinks.classList.remove("open");
    menuToggle.setAttribute("aria-expanded", "false");
  });
});


/* =========================
   REVEAL ANIMATION
========================= */

const revealObserver = new IntersectionObserver(
  (entries, observer) => {

    entries.forEach(entry => {

      if (entry.isIntersecting) {

        entry.target.classList.add("visible");

        observer.unobserve(entry.target);

      }

    });

  },
  {
    threshold: 0.12
  }
);

document
  .querySelectorAll(".reveal")
  .forEach(element => {

    revealObserver.observe(element);

  });


/* =========================
   COUNTER
========================= */

const counters =
  document.querySelectorAll("[data-count]");

const counterObserver =
  new IntersectionObserver(
    (entries, observer) => {

      entries.forEach(entry => {

        if (!entry.isIntersecting) return;

        const element = entry.target;

        const target =
          Number(element.dataset.count);

        const duration = 1200;

        const start =
          performance.now();

        function update(now) {

          const progress =
            Math.min(
              (now - start) / duration,
              1
            );

          const eased =
            1 - Math.pow(1 - progress, 3);

          element.textContent =
            Math.floor(eased * target);

          if (progress < 1) {

            requestAnimationFrame(update);

          } else {

            element.textContent = target;

          }

        }

        requestAnimationFrame(update);

        observer.unobserve(element);

      });

    },
    {
      threshold: 0.6
    }
  );

counters.forEach(counter => {

  counterObserver.observe(counter);

});


/* =========================
   PORTFOLIO FILTER
========================= */

const filters =
  document.querySelectorAll(".filter");

const portfolioItems =
  document.querySelectorAll(".portfolio-item");

filters.forEach(button => {

  button.addEventListener("click", () => {

    filters.forEach(filter => {

      filter.classList.remove("active");

    });

    button.classList.add("active");

    const selectedCategory =
      button.dataset.filter;

    portfolioItems.forEach(item => {

      const category =
        item.dataset.category;

      const match =
        selectedCategory === "all" ||
        category === selectedCategory;

      item.classList.toggle(
        "hidden",
        !match
      );

    });

  });

});


/* =========================
   LIGHTBOX
========================= */

const lightbox =
  document.getElementById("lightbox");

const lightboxImage =
  document.getElementById("lightboxImage");

const lightboxCaption =
  document.getElementById("lightboxCaption");

const lightboxClose =
  document.getElementById("lightboxClose");


portfolioItems.forEach(item => {

  item.addEventListener("click", () => {

    const image =
      item.querySelector("img");

    lightboxImage.src =
      image.src;

    lightboxImage.alt =
      image.alt;

    lightboxCaption.textContent =
      `${item.dataset.category} — ${item.dataset.title}`;

    lightbox.classList.add("open");

    lightbox.setAttribute(
      "aria-hidden",
      "false"
    );

    document.body.classList.add(
      "lightbox-open"
    );

  });

});


function closeLightbox() {

  lightbox.classList.remove("open");

  lightbox.setAttribute(
    "aria-hidden",
    "true"
  );

  document.body.classList.remove(
    "lightbox-open"
  );

}


lightboxClose.addEventListener(
  "click",
  closeLightbox
);


lightbox.addEventListener(
  "click",
  event => {

    if (event.target === lightbox) {

      closeLightbox();

    }

  }
);


document.addEventListener(
  "keydown",
  event => {

    if (event.key === "Escape") {

      closeLightbox();

    }

  }
);


/* =========================
   CURSOR GLOW
========================= */

const glow =
  document.querySelector(".cursor-glow");

window.addEventListener(
  "pointermove",
  event => {

    glow.style.left =
      event.clientX + "px";

    glow.style.top =
      event.clientY + "px";

  }
);


/* =========================
   CURRENT YEAR
========================= */

document.getElementById(
  "year"
).textContent =
  new Date().getFullYear();
"use strict";

const navbar = document.getElementById("navbar");
const menuToggle = document.getElementById("menuToggle");
const navLinks = document.getElementById("navLinks");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function closeMenu() {
  navLinks.classList.remove("open");
  menuToggle.setAttribute("aria-expanded", "false");
  menuToggle.setAttribute("aria-label", "Buka menu");
}
function updateNavbar() {
  navbar.classList.toggle("scrolled", window.scrollY > 30);
}
window.addEventListener("scroll", updateNavbar, { passive: true });
updateNavbar();
menuToggle.addEventListener("click", () => {
  const open = navLinks.classList.toggle("open");
  menuToggle.setAttribute("aria-expanded", String(open));
  menuToggle.setAttribute("aria-label", open ? "Tutup menu" : "Buka menu");
});
navLinks.querySelectorAll("a").forEach(link => link.addEventListener("click", closeMenu));
document.addEventListener("click", event => {
  if (!navbar.contains(event.target)) closeMenu();
});
window.matchMedia("(min-width: 651px)").addEventListener("change", closeMenu);

// Tanpa JavaScript atau IntersectionObserver, seluruh konten tetap terbaca.
if ("IntersectionObserver" in window && !reducedMotion) {
  const revealObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  document.querySelectorAll(".reveal").forEach(element => {
    element.classList.add("reveal-ready");
    revealObserver.observe(element);
  });
  const counterObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const element = entry.target;
      const target = Number(element.dataset.count);
      const start = performance.now();
      function update(now) {
        const progress = Math.min((now - start) / 1200, 1);
        element.textContent = Math.floor((1 - Math.pow(1 - progress, 3)) * target);
        if (progress < 1) requestAnimationFrame(update);
      }
      requestAnimationFrame(update);
      observer.unobserve(element);
    });
  }, { threshold: 0.6 });
  document.querySelectorAll("[data-count]").forEach(element => counterObserver.observe(element));
}

const filters = document.querySelectorAll(".filter");
const portfolioItems = document.querySelectorAll(".portfolio-item");
filters.forEach(button => button.addEventListener("click", () => {
  filters.forEach(filter => {
    const active = filter === button;
    filter.classList.toggle("active", active);
    filter.setAttribute("aria-pressed", String(active));
  });
  portfolioItems.forEach(item => {
    item.classList.toggle("hidden", button.dataset.filter !== "all" && item.dataset.category !== button.dataset.filter);
  });
}));

const lightbox = document.getElementById("lightbox");
const lightboxImage = document.getElementById("lightboxImage");
const lightboxCaption = document.getElementById("lightboxCaption");
const lightboxClose = document.getElementById("lightboxClose");
let previousFocus = null;
const backgroundElements = [...document.querySelectorAll("body > header, body > main, body > footer, body > .skip-link, body > .floating-booking")];
function openLightbox(item) {
  previousFocus = item;
  const image = item.querySelector("img");
  lightboxImage.src = image.src;
  lightboxImage.alt = image.alt;
  lightboxCaption.textContent = `${item.dataset.category} ? ${item.dataset.title}`;
  lightbox.classList.add("open");
  lightbox.setAttribute("aria-hidden", "false");
  document.body.classList.add("lightbox-open");
  backgroundElements.forEach(element => { element.inert = true; });
  lightboxClose.focus();
}
function closeLightbox() {
  if (!lightbox.classList.contains("open")) return;
  lightbox.classList.remove("open");
  lightbox.setAttribute("aria-hidden", "true");
  document.body.classList.remove("lightbox-open");
  backgroundElements.forEach(element => { element.inert = false; });
  previousFocus?.focus();
}
portfolioItems.forEach(item => {
  item.setAttribute("aria-label", `Lihat foto ${item.dataset.title}`);
  item.addEventListener("click", () => openLightbox(item));
  item.addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openLightbox(item);
    }
  });
});
lightboxClose.addEventListener("click", closeLightbox);
lightbox.addEventListener("click", event => {
  if (event.target === lightbox) closeLightbox();
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    closeLightbox();
    if (navLinks.classList.contains("open")) {
      closeMenu();
      menuToggle.focus();
    }
  }
  if (event.key === "Tab" && lightbox.classList.contains("open")) {
    event.preventDefault();
    lightboxClose.focus();
  }
});

const glow = document.querySelector(".cursor-glow");
if (glow && !reducedMotion && window.matchMedia("(pointer: fine)").matches) {
  window.addEventListener("pointermove", event => {
    glow.style.left = `${event.clientX}px`;
    glow.style.top = `${event.clientY}px`;
  }, { passive: true });
}
document.getElementById("year").textContent = new Date().getFullYear();

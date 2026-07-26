// Bridge between an embedded demo and the docs page hosting it.
//
// Posts the document height whenever it changes so the host can size the
// iframe, and accepts a theme message so the demo follows the docs theme
// toggle. Both directions are same-origin: the host is the docs site itself.

(function () {
  function postHeight() {
    var height = Math.ceil(document.documentElement.getBoundingClientRect().height);
    parent.postMessage({ type: "celeris-demo-height", height: height }, "*");
  }

  if (typeof ResizeObserver === "function") {
    new ResizeObserver(postHeight).observe(document.documentElement);
  }
  window.addEventListener("load", postHeight);

  window.addEventListener("message", function (event) {
    var data = event.data;
    if (!data || data.type !== "celeris-demo-theme") return;
    if (data.theme === "dark" || data.theme === "light") {
      document.documentElement.dataset.theme = data.theme;
    }
  });

  // The host may set the initial theme in the URL so the first paint matches.
  var initial = new URLSearchParams(location.search).get("theme");
  if (initial === "dark" || initial === "light") {
    document.documentElement.dataset.theme = initial;
  }
})();

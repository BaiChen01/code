(function () {
  const status = document.getElementById("statusPill");
  if (status) {
    status.textContent = "Legacy";
  }

  const heroText = document.querySelector(".hero-text");
  if (heroText) {
    heroText.textContent =
      "这是后端自带的静态兼容页。正式的 Vue 联调前端位于 frontend/ 目录，请通过 npm run dev 启动。";
  }
})();

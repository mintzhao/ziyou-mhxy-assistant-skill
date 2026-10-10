/* Keep the original equipment and resource tools independent. */
(function () {
  'use strict';
  function choose() {
    const resourceOnly = location.hash === '#resources-section' || location.hash.startsWith('#mhxy-intake=');
    document.body.classList.toggle('resource-only', resourceOnly);
    if (resourceOnly) {
      const details = document.querySelector('#resources-section details');
      if (details) details.open = true;
      document.title = '资源数量与成本 · 自游·梦幻助手（基础版）';
    } else document.title = '装备方案取舍 · 自游·梦幻助手（基础版）';
  }
  choose();
  window.addEventListener('hashchange', choose);
}());

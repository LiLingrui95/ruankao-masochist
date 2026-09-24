'use strict';

(function exposeBinarySearch(root) {
  const values = Object.freeze([4, 11, 19, 28, 36, 47, 59]);

  function makeStep(phase, low, high, mid, target, message, result = null) {
    return Object.freeze({phase, low, high, mid, target, message, result});
  }

  function buildTrace(target) {
    if (target !== 47 && target !== 35) throw new Error('Unsupported binary-search target');
    const steps = [makeStep('initial', 0, values.length - 1, null, target, '若目标存在，其位置一定在当前闭区间内；先确定左右边界。')];
    let low = 0, high = values.length - 1;
    while (low <= high) {
      const mid = low + Math.floor((high - low) / 2);
      steps.push(makeStep('compare', low, high, mid, target, `比较目标 ${target} 与 a[${mid}] = ${values[mid]}。`));
      if (values[mid] === target) {
        steps.push(makeStep('terminal', low, high, mid, target, `命中下标 ${mid}，返回 ${mid}。`, mid));
        return Object.freeze(steps);
      }
      if (values[mid] < target) {
        low = mid + 1;
        steps.push(makeStep('update', low, high, null, target, `目标更大，排除 mid 及其左侧，low 更新为 ${low}。`));
      } else {
        high = mid - 1;
        steps.push(makeStep('update', low, high, null, target, `目标更小，排除 mid 及其右侧，high 更新为 ${high}。`));
      }
    }
    steps.push(makeStep('terminal', low, high, null, target, `区间为空（low=${low}，high=${high}），返回 -1。`, -1));
    return Object.freeze(steps);
  }

  const api = Object.freeze({values, buildTrace});
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.BinarySearchDiagram = api;
})(typeof globalThis === 'object' ? globalThis : this);

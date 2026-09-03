export function nextFamilyAttentionState(realMode, currentState) {
  return realMode ? currentState : !currentState
}

export function presentElderTripActionHint(realMode, isTripActive) {
  if (isTripActive) return '确认安全到家后点击'
  return realMode ? '开始后等待定位数据上报' : '演示：开始后显示模拟定位'
}

'use strict'

const NETWORK_MESSAGE = '当前网络异常，请稍后重试'

function userFacingError(error, fallback = '操作失败，请稍后重试') {
  if (error?.code === 'NETWORK_ERROR' || error?.code === 'REQUEST_UNSUPPORTED') {
    return NETWORK_MESSAGE
  }
  if (error?.code === 'API_DISABLED') {
    return '服务地址未配置，请联系测试管理员'
  }
  if (error?.status === 401) {
    return error?.code === 'INVALID_CREDENTIALS'
      ? '账号或密码错误，请重新输入'
      : '登录状态已失效，请重新登录'
  }
  if (Number(error?.status) >= 500) return NETWORK_MESSAGE
  return fallback
}

module.exports = {
  NETWORK_MESSAGE,
  userFacingError
}

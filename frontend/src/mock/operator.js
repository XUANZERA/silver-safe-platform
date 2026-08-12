export const operatorOverview = {
  resolvedBeforeDemo: 10,
}

export const alerts = [
  {
    id: 301,
    level: 'urgent',
    type: 'SOS 紧急求助',
    elderName: '周明远',
    location: '银杏公园东门附近',
    time: '10:24',
    status: '待处理',
  },
  {
    id: 302,
    level: 'warning',
    type: '离开安全区域',
    elderName: '许兰芝',
    location: '春晖路与安康街交叉口',
    time: '10:17',
    status: '处理中',
  },
  {
    id: 303,
    level: 'warning',
    type: '定位长时间未更新',
    elderName: '陈怀安',
    location: '滨河步道南段',
    time: '09:56',
    status: '待处理',
  },
]

export const trips = [
  { id: 501, elderName: '叶舒云', destination: '市民文化中心', startedAt: '09:42', duration: '48 分钟', state: '正常', status: '进行中', contact: '家属：叶晨 188****1032' },
  { id: 502, elderName: '沈文海', destination: '惠民社区医院', startedAt: '09:18', duration: '1 小时 12 分', state: '正常', status: '进行中', contact: '家属：沈欣 188****4671' },
  { id: 503, elderName: '许兰芝', destination: '春晖便民市场', startedAt: '08:55', duration: '1 小时 35 分', state: '需关注', status: '进行中', contact: '家属：许宁 188****8260' },
  { id: 504, elderName: '周明远', destination: '银杏公园', startedAt: '08:20', duration: '2 小时 05 分', state: '告警中', status: '进行中', contact: '家属：周禾 188****3348' },
  { id: 505, elderName: '陈怀安', destination: '滨河步道', startedAt: '07:55', duration: '1 小时 21 分', state: '已结束', status: '已完成', contact: '家属：陈清 188****5924' },
]

export const elders = [
  { id: 101, name: '叶舒云', age: 71, gender: '女', phone: '188****4126', family: '叶晨', familyPhone: '188****1032', status: '出游中', risk: '低风险', lastLocation: '市民文化中心', updatedAt: '刚刚' },
  { id: 102, name: '沈文海', age: 68, gender: '男', phone: '188****7350', family: '沈欣', familyPhone: '188****4671', status: '出游中', risk: '低风险', lastLocation: '惠民社区医院', updatedAt: '1 分钟前' },
  { id: 103, name: '许兰芝', age: 74, gender: '女', phone: '188****2861', family: '许宁', familyPhone: '188****8260', status: '需关注', risk: '中风险', lastLocation: '春晖路与安康街交叉口', updatedAt: '2 分钟前' },
  { id: 104, name: '周明远', age: 76, gender: '男', phone: '188****9642', family: '周禾', familyPhone: '188****3348', status: '告警中', risk: '高风险', lastLocation: '银杏公园东门附近', updatedAt: '刚刚' },
  { id: 105, name: '陈怀安', age: 70, gender: '男', phone: '188****1579', family: '陈清', familyPhone: '188****5924', status: '在家', risk: '低风险', lastLocation: '滨河社区 3 号楼', updatedAt: '18 分钟前' },
  { id: 106, name: '林静秋', age: 66, gender: '女', phone: '188****6083', family: '林悦', familyPhone: '188****6083', status: '在家', risk: '低风险', lastLocation: '安和社区 8 号楼', updatedAt: '32 分钟前' },
]

export const alertHistory = [
  { id: 290, level: 'warning', type: '短时离开安全区域', elderName: '林静秋', location: '安和社区南门', time: '昨天 16:40', status: '已解决', familyContact: '林悦 188****6083', resolution: '已联系本人确认安全并返回围栏范围' },
  { id: 287, level: 'urgent', type: 'SOS 紧急求助', elderName: '沈文海', location: '惠民社区医院', time: '昨天 10:12', status: '已解决', familyContact: '沈欣 188****4671', resolution: '家属已到达现场，确认老人安全' },
]

你现在是 Senior QA Engineer。

项目：
银龄安全系统。

请不要修改代码。

目标：
验证当前阶段是否真实可运行。

执行原则：

1. 先读取：
docs/ai/

2. 查看：
git status
git log -10
git diff


3. 不要相信已有测试报告。

重新执行。


测试必须分层：


Phase 1:
环境检查

检查：
- Python环境
- Node环境
- 环境变量
- 数据库


Phase 2:
自动化测试

执行：
backend pytest
miniprogram npm test


记录：
实际命令
实际输出


Phase 3:
API smoke test

启动服务。

验证：

用户登录
token获取
权限验证
核心接口


Phase 4:
业务闭环

模拟：

老人:
登录
获取trip
上传location

家属:
登录
查看safety


验证：

risk_status
location_health


Phase 5:
安全测试

验证：

越权访问
错误token
非法参数


输出：

不要写"应该通过"

只能写：

PASS:
有实际输出支持

FAIL:
有错误日志


最后输出：

Testing Report

1. Passed
2. Failed
3. Risks
4. Next steps
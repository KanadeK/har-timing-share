# har-timing-share 中文说明

把 HAR 转换成只保留性能轮廓的离线 HTML 瀑布图或 JSON。需要 Python 3.10+，
没有运行时第三方依赖。安装：在源码目录执行 `python -m pip install .`。

```console
har-timing-share examples/demo.har -o performance.html
har-timing-share examples/demo.har --format json -o performance.json
```

打开 HTML 即可查看。示例为合成数据：3 个请求、350 ms 时间跨度、中位数 120 ms、
95 分位 250 ms、1 个 HTTP 错误、1,800 个已知解码字节、1 个未知大小。
工具不会覆盖已有文件，重复执行需更换输出路径。

输出仅保留固定的请求编号、方法/资源类别、状态码、相对时间、阶段时间和解码体积。
URL、域名、路径、Cookie、请求头、正文、IP、绝对时间及扩展字段全部丢弃。
它生成的是派生报告，不能作为 HAR 回放。性能数据仍可能识别会话，分享前请检查。

默认输入上限 64 MiB、请求数上限 10,000，可通过 `--max-bytes` / `--max-entries` 调整。
拒绝损坏 JSON、重复对象键、非有限数值、异常状态码和无时区日期等输入。
不发送网络请求，不上传数据。原始 HAR 仍保留在用户磁盘和处理过程内存中。

退出码：0 已生成报告；2 输入/输出错误；130 处理时中断。
`python -m har_timing_share` 可替代命令。`python -m pip uninstall har-timing-share` 卸载，
自行删除生成报告和虚拟环境即可清理。完整字段语义和限制见 [英文 README](README.md)。
MIT 许可证，版本 0.1.0。

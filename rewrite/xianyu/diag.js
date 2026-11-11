/*
 * 闲鱼诊断（Loon generic 脚本，诊断用）
 *
 * 读取 capture.js 采集到的接口地址，写进脚本日志、弹一条通知，
 * 并把完整列表放进剪贴板。通知正文只放前 200 字，完整内容点通知复制。
 * 读完即清空，方便下一轮重新采集。
 */

(function () {
    var KEY = "xianyu_diag_urls";
    var list = [];
    try {
        list = JSON.parse($persistentStore.read(KEY) || "[]") || [];
    } catch (e) {
        list = [];
    }
    var text = list.length
        ? list.join("\n")
        : "(还没采到：先打开闲鱼刷几下首页、搜个东西，再执行本脚本)";

    console.log(text);
    $notification.post(
        "闲鱼诊断",
        list.length + " 条接口",
        text.slice(0, 200),
        { clipboard: text }
    );
    $persistentStore.write("[]", KEY);
    $done({});
})();

/*
 * 闲鱼接口采集（Loon，诊断用）
 *
 * 只记录 URL，不读、不改任何响应体，也不发网络请求。
 * 采到的地址去参数后存进 $persistentStore，最多 60 条、去重、新的在前。
 * 配合 diag.js 用：Loon 里手动执行「闲鱼诊断」即可把列表复制到剪贴板。
 *
 * 注意：Loon 的 Response Script 同一响应只执行一条，所以这条在 [Script] 里
 * 必须排在真正的去广告脚本之后，否则会把它们饿死。
 */

(function () {
    var KEY = "xianyu_diag_urls";
    try {
        var list = [];
        var raw = $persistentStore.read(KEY);
        if (raw) {
            try { list = JSON.parse(raw) || []; } catch (e) { list = []; }
        }
        var url = ($request && $request.url ? $request.url : "").split("?")[0];
        if (url) {
            list = list.filter(function (u) { return u !== url; });
            list.unshift(url);
            if (list.length > 60) list = list.slice(0, 60);
            $persistentStore.write(JSON.stringify(list), KEY);
        }
    } catch (e) {
        console.log("[闲鱼采集] " + e);
    }
    $done({});
})();

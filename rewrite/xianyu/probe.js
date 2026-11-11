/*
 * 闲鱼响应探针（Loon，诊断用）
 *
 * 目的只有一个：告诉我们「哪个接口、哪个数组、哪个字段」还在下发广告。
 * 只读不写——不修改任何响应体，$done({}) 原样放行。
 *
 * 输出到脚本日志（Loon → 请求记录 → 点开任意 goofish 请求 → 日志）。
 * 每次执行都会输出累计汇总，所以随便点开哪一条都能看到全貌。
 * 用 Request 阶段拿不到 body，所以这条是 Response 脚本；必须排在 6 条去广告脚本之后，
 * 否则「同一响应只执行一条 Response Script」会把它们饿死。
 */

(function () {
    var KEY = "xianyu_probe_map";
    var MAX = 24;
    var LIMIT = 1600;   // 日志长度上限，避免被截断

    // 已由 adblock.list 固化规则覆盖的接口
    var RULED = [
        "mtop.taobao.idlehome.home.nextfresh",
        "mtop.taobao.idlehome.widget.refresh.get",
        "mtop.taobao.idlehome.magic.home.page.list",
        "mtop.taobao.idlehome.home.community",
        "mtop.taobao.idlehome.home.newitem.page",
        "mtop.taobao.idle.home.whale.modulet",
        "mtop.taobao.idle.fun.follow.feed.list",
        "mtop.taobao.idle.item.recommend.list",
        "mtop.taobao.idle.playboy.recommend",
        "mtop.taobao.idle.user.page.my.adapter",
        "mtop.taobao.idle.local.near.by.corner.info",
        "mtop.taobao.idle.local.flow.plat.section",
        "mtop.taobao.idle.local.home.top",
        "mtop.taobao.idle.local.home",
        "mtop.taobao.idle.item.buy.feeds",
        "mtop.taobao.idle.trade.full.info",
        "mtopsearch.search.shade",
        "mtopsearch.search.discover",
        "mtopsearch.search.activate",
        "mtopsearch.search"
    ];

    // 已由 [Script] 里的脚本处理的接口
    var SCRIPTED = [
        "idlecommerce.splash",
        "idleadv.app.launch.report",
        "idleadv.scene.restore",
        "mtop.idle.ad.expose",
        "idle.user.strategy.list",
        "idlehome.home.circle.list"
    ];

    var SUS = /^(is?ad|ad_?type|adtype|ads|adinfo|adid|dsp|promo|sponsor|marketing|creative|biztype|cardtype|template)/i;

    function matchAny(u, arr) {
        for (var i = 0; i < arr.length; i++) if (u.indexOf(arr[i]) >= 0) return true;
        return false;
    }

    function shortPath(u) {
        var s = u.split("?")[0];
        var m = s.match(/\/(mtop[\w.]*|mtopsearch[\w.]*)/);
        if (m) return m[1];
        m = s.match(/^https?:\/\/([^/]+)(\/[^?]*)?/);
        return m ? (m[1] + (m[2] || "")) : s;
    }

    // 递归找「可疑数组」：数组元素里出现广告相关字段
    function scan(node, path, depth, out) {
        if (!node || depth > 4 || out.length > 12) return;
        if (Array.isArray(node)) {
            if (!node.length) return;
            var keys = {};
            for (var i = 0; i < Math.min(node.length, 5); i++) {
                var el = node[i];
                if (el && typeof el === "object") {
                    for (var k in el) keys[k] = 1;
                }
            }
            var sus = [];
            for (var kk in keys) if (SUS.test(kk)) sus.push(kk);
            if (sus.length) out.push(path + "[" + node.length + "]{" + sus.join(",") + "}");
            for (var j = 0; j < Math.min(node.length, 2); j++) scan(node[j], path + "." + j, depth + 1, out);
        } else if (typeof node === "object") {
            var n = 0;
            for (var k2 in node) {
                if (n++ > 30) break;
                scan(node[k2], path + "." + k2, depth + 1, out);
            }
        }
    }

    try {
        var url = ($request && $request.url) ? $request.url : "";
        if (!url) { $done({}); return; }

        var name = shortPath(url);
        var body = ($response && $response.body) ? $response.body : "";
        var json = null;
        try { json = JSON.parse(body); } catch (e) { json = null; }

        var map = {};
        var raw = $persistentStore.read(KEY);
        if (raw) { try { map = JSON.parse(raw) || {}; } catch (e) { map = {}; } }

        var verdict;
        if (!json) {
            verdict = "非JSON/空(len=" + body.length + ")";
        } else {
            var data = (json.data !== undefined && json.data !== null) ? json.data : json;
            var hits = [];
            scan(data, "data", 0, hits);
            var ret = json.ret ? ("" + json.ret).slice(0, 40) : "";
            verdict = (hits.length ? hits.join(" ") : "无可疑数组") +
                " | top=" + Object.keys(json).slice(0, 6).join(",") +
                (ret ? " | ret=" + ret : "");
        }

        var tag = matchAny(url, RULED) ? "R" : (matchAny(url, SCRIPTED) ? "S" : "-");
        map[name] = "[" + tag + "] " + name + " => " + verdict;

        var names = Object.keys(map);
        if (names.length > MAX) {
            names.sort();
            for (var i = 0; i < names.length - MAX; i++) delete map[names[i]];
        }
        $persistentStore.write(JSON.stringify(map), KEY);

        var lines = ["[闲鱼探针] 累计 " + Object.keys(map).length + " 个接口（R=有固化规则 S=有脚本 -=都没有）"];
        var keys = Object.keys(map).sort();
        for (var n = 0; n < keys.length; n++) lines.push(map[keys[n]]);
        var text = lines.join("\n");
        if (text.length > LIMIT) text = text.slice(0, LIMIT) + "\n...(截断)";
        console.log(text);
    } catch (err) {
        console.log("[闲鱼探针] 异常: " + err);
    }

    $done({});
})();

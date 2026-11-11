/*
 * 闲鱼接口采集（Loon，诊断用，自动汇报）
 *
 * 只记录 URL，不读、不改任何请求或响应体，不发任何网络请求。
 * 作为 Request Script 挂载，和响应脚本不在一个池子里，不会抢跑去广告脚本。
 *
 * 行为：命中 goofish 域名的请求记一条（去 query、按完整 URL 去重，最多 200 条），
 * 顶部标注该接口是否在已固化规则覆盖范围内（✅ 已覆盖 / ❌ 未覆盖）。
 * 每攒够 GAP 毫秒就弹一条通知，点通知把完整列表写进剪贴板。
 * 诊断完把 [Script] 里这一行删掉即可。
 */

(function () {
    var KEY = "xianyu_diag_urls";
    var TSK = "xianyu_diag_ts";
    var MAX = 200;
    var GAP = 120 * 1000;   // 两次通知的最小间隔：2 分钟

    // adblock.list 里已固化的 20 个接口（写入时不要转义点号）
    var COVERED = [
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

    function isCovered(u) {
        for (var i = 0; i < COVERED.length; i++) {
            if (u.indexOf(COVERED[i]) >= 0) return true;
        }
        return false;
    }

    function report(list, extra) {
        var miss = list.filter(function (e) { return !e.c; });
        var lines = miss.map(function (e) { return "❌ " + e.u; })
            .concat(list.filter(function (e) { return e.c; })
                .map(function (e) { return "✅ " + e.u; }));
        var text = lines.join("\n");

        console.log("[闲鱼采集] " + list.length + " 条 / 未覆盖 " + miss.length + " 条\n" + text);

        $notification.post(
            "闲鱼诊断",
            list.length + " 条接口，其中 " + miss.length + " 条未被规则覆盖",
            (extra || "") + (miss.length
                ? miss.slice(0, 3).map(function (e) { return e.u; }).join("\n")
                : "全部命中已有规则"),
            { clipboard: text }
        );
    }

    try {
        var list = [];
        var raw = $persistentStore.read(KEY);
        if (raw) {
            try { list = JSON.parse(raw) || []; } catch (e) { list = []; }
        }

        var url = ($request && $request.url ? $request.url : "").split("?")[0];
        if (url) {
            var idx = -1;
            for (var i = 0; i < list.length; i++) {
                if (list[i] && list[i].u === url) { idx = i; break; }
            }
            var isNew = idx < 0;
            if (isNew) {
                list.unshift({ u: url, c: isCovered(url) });
                if (list.length > MAX) list = list.slice(0, MAX);
                $persistentStore.write(JSON.stringify(list), KEY);
            }

            var now = Date.now();
            var last = parseInt($persistentStore.read(TSK) || "0", 10) || 0;
            if (isNew && now - last > GAP) {
                $persistentStore.write(String(now), TSK);
                report(list, "");
            }
        }
    } catch (e) {
        console.log("[闲鱼采集] 异常: " + e);
    }

    $done({});
})();

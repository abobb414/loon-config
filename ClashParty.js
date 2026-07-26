/*
 * Clash Party dynamic override for abobb414/loon-config.
 *
 * The subscription supplies proxies. This file keeps the custom strategy and
 * rule logic from Stash.yaml, then builds a Mihomo-compatible config around it.
 */

const testUrl = "http://www.gstatic.com/generate_204";
const interval = 600;

const icons = {
  global: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Global.png",
  static: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Static.png",
  direct: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Direct.png",
  finance: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Cryptocurrency_1.png",
  wechat: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/WeChat.png",
  ai: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/AI.png",
  openai: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/ChatGPT.png",
  gemini: "https://raw.githubusercontent.com/fmz200/wool_scripts/main/icons/apps/Gemini_01.png",
  claude: "https://raw.githubusercontent.com/abobb414/loon-config/main/IconSet/Color/Claude.png",
  google: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Google_Search.png",
  apple: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Apple.png",
  microsoft: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Microsoft.png",
  netflix: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Netflix.png",
  disney: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Disney.png",
  hbo: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/HBO.png",
  spotify: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Spotify.png",
  youtube: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/YouTube.png",
  bilibili: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/bilibili.png",
  tiktok: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/TikTok.png",
  douyin: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/TikTok_2.png",
  instagram: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Instagram.png",
  telegram: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Telegram.png",
  linkedin: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Linkedin.png",
  emby: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Emby.png",
  speedtest: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Speedtest.png",
  hk: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Hong_Kong.png",
  tw: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Taiwan.png",
  sg: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Singapore.png",
  jp: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Japan.png",
  kr: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Korea.png",
  us: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/United_States.png",
  au: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Australia.png",
  eu: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Europe_Map.png",
  as: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Asia_Map.png",
  am: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/America_Map.png",
  af: "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Africa_Map.png",
};

const regions = {
  HK: { icon: icons.hk, filter: "(?i)🇭🇰|香港|HK|Hong" },
  TW: { icon: icons.tw, filter: "(?i)🇨🇳|🇹🇼|台湾|TW|Taiwan" },
  SG: { icon: icons.sg, filter: "(?i)🇸🇬|新加坡|狮城|SG|Singapore" },
  JP: { icon: icons.jp, filter: "(?i)🇯🇵|日本|东京|大阪|JP|Japan" },
  KR: { icon: icons.kr, filter: "(?i)🇰🇷|韩国|首尔|KR|Korea" },
  US: { icon: icons.us, filter: "(?i)🇺🇸|美国|洛杉矶|圣何塞|西雅图|芝加哥|US|United States" },
  AU: { icon: icons.au, filter: "(?i)澳大利亚|澳洲|悉尼|墨尔本|布里斯班|珀斯|阿德莱德|Australia|Sydney|Melbourne|Brisbane|Perth|Adelaide|AU" },
  EU: { icon: icons.eu, filter: "(?i)(欧洲|欧盟|德国|法国|英国|荷兰|意大利|西班牙|葡萄牙|爱尔兰|比利时|卢森堡|瑞士|奥地利|波兰|捷克|斯洛伐克|匈牙利|罗马尼亚|保加利亚|希腊|乌克兰|白俄罗斯|俄罗斯|塞尔维亚|克罗地亚|斯洛文尼亚|波黑|阿尔巴尼亚|北马其顿|黑山|科索沃|摩尔多瓦|立陶宛|拉脱维亚|爱沙尼亚|马耳他|冰岛|挪威|瑞典|芬兰|丹麦|塞浦路斯|Europe|Germany|France|United Kingdom|Netherlands|Italy|Spain|Portugal|Ireland|Belgium|Luxembourg|Switzerland|Austria|Poland|Czech|Slovakia|Hungary|Romania|Bulgaria|Greece|Ukraine|Belarus|Russia|Serbia|Croatia|Slovenia|Bosnia|Albania|Macedonia|Montenegro|Kosovo|Moldova|Lithuania|Latvia|Estonia|Malta|Iceland|Norway|Sweden|Finland|Denmark|Cyprus|EU)" },
  AS: { icon: icons.as, filter: "(?i)^(?!.*(港|香港|HK|Hong|台|台湾|TW|Taiwan|日本|东京|大阪|JP|Japan|韩国|首尔|KR|Korea|新加坡|狮城|SG|Singapore|美国|洛杉矶|圣何塞|西雅图|芝加哥|US|United States|澳大利亚|澳洲|AU|Australia|悉尼|墨尔本|布里斯班|珀斯|阿德莱德|Sydney|Melbourne|Brisbane|Perth|Adelaide)).*(亚洲|土耳其|伊斯坦布尔|以色列|特拉维夫|沙特|利雅得|阿联酋|迪拜|卡塔尔|多哈|印度|新德里|孟买|巴基斯坦|伊朗|伊拉克|科威特|阿曼|巴林|约旦|黎巴嫩|哈萨克斯坦|乌兹别克斯坦|塔吉克斯坦|土库曼斯坦|格鲁吉亚|亚美尼亚|阿塞拜疆|蒙古|马来西亚|泰国|印度尼西亚|印尼|菲律宾|越南|柬埔寨|老挝|缅甸|文莱|孟加拉|斯里兰卡|尼泊尔|俄罗斯|Turkey|Israel|Saudi|United Arab Emirates|UAE|Qatar|India|Pakistan|Iran|Iraq|Kuwait|Oman|Bahrain|Jordan|Lebanon|Kazakhstan|Uzbekistan|Kyrgyzstan|Tajikistan|Turkmenistan|Georgia|Armenia|Azerbaijan|Mongolia|Malaysia|Thailand|Indonesia|Philippines|Vietnam|Cambodia|Laos|Myanmar|Brunei|Bangladesh|Sri Lanka|Nepal|Russia)" },
  AM: { icon: icons.am, filter: "(?i)^(?!.*(美国|洛杉矶|圣何塞|西雅图|芝加哥|US|United States)).*(美洲|北美|南美|加拿大|多伦多|温哥华|蒙特利尔|墨西哥|墨西哥城|巴西|阿根廷|智利|哥伦比亚|秘鲁|乌拉圭|厄瓜多尔|玻利维亚|巴拉圭|委内瑞拉|圭亚那|苏里南|Canada|Toronto|Vancouver|Montreal|Mexico|Mexico City|Brazil|Argentina|Chile|Colombia|Peru|Uruguay|Ecuador|Bolivia|Paraguay|Venezuela|Guyana|Suriname|North America|South America|America)" },
  AF: { icon: icons.af, filter: "(?i)(非洲|南非|开普敦|约翰内斯堡|埃及|开罗|尼日利亚|拉各斯|肯尼亚|内罗毕|摩洛哥|卡萨布兰卡|突尼斯|阿尔及利亚|加纳|埃塞俄比亚|坦桑尼亚|乌干达|卢旺达|津巴布韦|赞比亚|博茨瓦纳|纳米比亚|安哥拉|塞内加尔|毛里求斯|South Africa|Egypt|Nigeria|Kenya|Morocco|Tunisia|Algeria|Ghana|Ethiopia|Tanzania|Uganda|Rwanda|Zimbabwe|Zambia|Botswana|Namibia|Angola|Senegal|Mauritius)" },
};

const regionsForProxy = ["HK", "SG", "JP", "KR", "US", "AU", "TW", "EU", "AS", "AM", "AF"];
const aiRegions = ["US", "AU", "JP", "SG", "TW", "KR", "EU", "AS", "AM", "AF"];

function testGroup(name, icon, filter) {
  return {
    name,
    icon,
    type: "url-test",
    "include-all": true,
    url: testUrl,
    interval,
    tolerance: 50,
    filter,
  };
}

function serviceGroup(name, icon, proxies) {
  return { name, icon, type: "select", proxies };
}

function buildProxyGroups() {
  const groups = [
    serviceGroup("Proxy", icons.global, ["Available", ...regionsForProxy]),
    { name: "Available", icon: icons.static, type: "url-test", "include-all": true, url: testUrl, interval, tolerance: 50, filter: "^(?!.*网易云)" },
    serviceGroup("Final", icons.direct, ["Proxy", "DIRECT"]),
    serviceGroup("Finance", icons.finance, ["DIRECT", "Proxy"]),
    serviceGroup("WeChat", icons.wechat, ["DIRECT", "Proxy"]),
    testGroup("AI", icons.ai, "(?i)^(?!.*(港|香港|HK|Hong)).*(美国|洛杉矶|圣何塞|西雅图|芝加哥|US|United States|日本|东京|大阪|JP|Japan|新加坡|狮城|SG|Singapore|台|台湾|TW|Taiwan|韩国|首尔|KR|Korea|欧洲|欧盟|德国|法国|英国|荷兰|意大利|西班牙|EU|Europe)"),
    serviceGroup("OpenAI", icons.openai, ["AI", ...aiRegions]),
    serviceGroup("Gemini", icons.gemini, ["AI", ...aiRegions]),
    serviceGroup("Claude", icons.claude, ["AI", ...aiRegions]),
    serviceGroup("Google", icons.google, ["Proxy", ...regionsForProxy]),
    serviceGroup("Apple", icons.apple, ["DIRECT", "Proxy", ...regionsForProxy]),
    serviceGroup("Microsoft", icons.microsoft, ["DIRECT", "Proxy", ...regionsForProxy]),
    serviceGroup("Netflix", icons.netflix, ["Proxy", "US", "AU", "SG", "JP", "HK", "TW", "KR", "EU", "AS", "AM", "AF"]),
    serviceGroup("Disney", icons.disney, ["Proxy", "US", "AU", "SG", "JP", "HK", "TW", "KR", "EU", "AS", "AM", "AF"]),
    serviceGroup("HBO", icons.hbo, ["Proxy", "US", "AU", "SG", "HK", "TW", "JP", "KR", "EU", "AS", "AM", "AF"]),
    serviceGroup("Spotify", icons.spotify, ["Proxy", "DIRECT", "US", "AU", "SG", "JP", "HK", "TW", "KR", "EU", "AS", "AM", "AF"]),
    serviceGroup("YouTube", icons.youtube, ["Proxy", "US", "AU", "SG", "JP", "HK", "TW", "KR", "EU", "AS", "AM", "AF"]),
    serviceGroup("Bilibili", icons.bilibili, ["DIRECT", "Proxy", "HK", "TW", "SG", "JP", "KR", "US", "AU", "EU", "AS", "AM", "AF"]),
    serviceGroup("TikTok", icons.tiktok, ["Proxy", "US", "AU", "SG", "JP", "HK", "TW", "KR", "EU", "AS", "AM", "AF"]),
    serviceGroup("Douyin", icons.douyin, ["DIRECT", "Proxy"]),
    serviceGroup("Instagram", icons.instagram, ["Proxy", "US", "AU", "SG", "JP", "HK", "TW", "KR", "EU", "AS", "AM", "AF"]),
    serviceGroup("Telegram", icons.telegram, ["Proxy", "SG", "US", "AU", "HK", "JP", "TW", "KR", "EU", "AS", "AM", "AF"]),
    serviceGroup("LinkedIn", icons.linkedin, ["Proxy", "DIRECT", "US", "AU", "SG", "JP", "HK", "TW", "KR", "EU", "AS", "AM", "AF"]),
    serviceGroup("Emby", icons.emby, ["Proxy", "US", "AU", "SG", "JP", "HK", "TW", "KR", "EU", "AS", "AM", "AF"]),
    serviceGroup("SpeedtestChina", icons.speedtest, ["DIRECT", "Proxy"]),
    serviceGroup("SpeedtestInternational", icons.speedtest, ["Proxy", "DIRECT"]),
  ];

  for (const [name, region] of Object.entries(regions)) {
    groups.push(testGroup(name, region.icon, region.filter));
  }
  return groups;
}

const ruleProviders = {
  Reject: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Advertising/Advertising.yaml" },
  AppleUpdate: { behavior: "classical", format: "text", interval: 86400, url: "https://github.com/fmz200/wool_scripts/raw/main/Loon/rule/apple_update.list" },
  RejectAds: { behavior: "classical", format: "text", interval: 86400, url: "https://github.com/fmz200/wool_scripts/raw/main/Loon/rule/rejectAd.list" },
  AdRules: { behavior: "classical", format: "text", interval: 86400, url: "https://raw.githubusercontent.com/Cats-Team/AdRules/main/adrules.list" },
  SpeedtestChina: { behavior: "classical", format: "yaml", interval: 86400, url: "https://kelee.one/Tool/Clash/Rule/SpeedtestChina.yaml" },
  SpeedtestInternational: { behavior: "classical", format: "yaml", interval: 86400, url: "https://kelee.one/Tool/Clash/Rule/SpeedtestInternational.yaml" },
  Direct: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Direct/Direct.yaml" },
  ChinaMaxNoIP: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/ChinaMaxNoIP/ChinaMaxNoIP.yaml" },
  Proxy: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Proxy/Proxy.yaml" },
  WeChat: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/WeChat/WeChat.yaml" },
  AliPay: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/AliPay/AliPay.yaml" },
  UnionPay: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/UnionPay/UnionPay.yaml" },
  ICBC: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/ICBC/ICBC.yaml" },
  CCB: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/CCB/CCB.yaml" },
  BOC: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/BOC/BOC.yaml" },
  ABC: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/ABC/ABC.yaml" },
  CMB: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/CMB/CMB.yaml" },
  BOCOM: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/BOCOM/BOCOM.yaml" },
  CEB: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/CEB/CEB.yaml" },
  YouTube: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/YouTube/YouTube.yaml" },
  AI: { behavior: "classical", format: "text", interval: 86400, url: "https://github.com/fmz200/wool_scripts/raw/main/Loon/rule/AI.list" },
  OpenAI: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/OpenAI/OpenAI.yaml" },
  Gemini: { behavior: "classical", format: "text", interval: 86400, url: "https://raw.githubusercontent.com/abobb414/loon-config/main/rules/Gemini.list" },
  Claude: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Claude/Claude.yaml" },
  Google: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Google/Google.yaml" },
  Apple: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Apple/Apple.yaml" },
  Microsoft: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Microsoft/Microsoft.yaml" },
  Netflix: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Netflix/Netflix.yaml" },
  Disney: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Disney/Disney.yaml" },
  HBO: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/HBO/HBO.yaml" },
  Spotify: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Spotify/Spotify.yaml" },
  Bilibili: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/BiliBili/BiliBili.yaml" },
  TikTok: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/TikTok/TikTok.yaml" },
  Douyin: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/DouYin/DouYin.yaml" },
  Instagram: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Instagram/Instagram.yaml" },
  Telegram: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Telegram/Telegram.yaml" },
  LinkedIn: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/LinkedIn/LinkedIn.yaml" },
  Emby: { behavior: "classical", format: "yaml", interval: 86400, url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Emby/Emby.yaml" },
};

const rules = [
  "DOMAIN,iris.niceduck.lol,DIRECT",
  "DOMAIN,cf.iris520.vip,DIRECT",
  "DOMAIN,cdn.liminalnet.team,DIRECT",
  "DOMAIN,limina.552554.xyz,DIRECT",
  "RULE-SET,Reject,REJECT",
  "RULE-SET,AppleUpdate,REJECT",
  "RULE-SET,RejectAds,REJECT",
  "RULE-SET,AdRules,REJECT",
  "RULE-SET,SpeedtestChina,SpeedtestChina",
  "RULE-SET,SpeedtestInternational,SpeedtestInternational",
  "RULE-SET,WeChat,WeChat",
  "RULE-SET,AliPay,Finance",
  "RULE-SET,UnionPay,Finance",
  "RULE-SET,ICBC,Finance",
  "RULE-SET,CCB,Finance",
  "RULE-SET,BOC,Finance",
  "RULE-SET,ABC,Finance",
  "RULE-SET,CMB,Finance",
  "RULE-SET,BOCOM,Finance",
  "RULE-SET,CEB,Finance",
  "RULE-SET,YouTube,YouTube",
  "RULE-SET,OpenAI,OpenAI",
  "RULE-SET,Gemini,Gemini",
  "RULE-SET,Claude,Claude",
  "RULE-SET,Google,Google",
  "RULE-SET,Apple,Apple",
  "RULE-SET,AI,AI",
  "RULE-SET,Microsoft,Microsoft",
  "RULE-SET,Netflix,Netflix",
  "RULE-SET,Disney,Disney",
  "RULE-SET,HBO,HBO",
  "RULE-SET,Spotify,Spotify",
  "RULE-SET,Bilibili,Bilibili",
  "RULE-SET,TikTok,TikTok",
  "RULE-SET,Douyin,Douyin",
  "RULE-SET,Instagram,Instagram",
  "RULE-SET,Telegram,Telegram",
  "RULE-SET,LinkedIn,LinkedIn",
  "RULE-SET,Emby,Emby",
  "RULE-SET,Direct,DIRECT",
  "RULE-SET,ChinaMaxNoIP,DIRECT",
  "GEOIP,CN,DIRECT",
  "RULE-SET,Proxy,Proxy",
  "MATCH,Final",
];

function main(input) {
  if (!input || !Array.isArray(input.proxies)) {
    throw new Error("Clash Party subscription must provide a proxies array");
  }

  const output = { ...input };
  delete output["proxy-providers"];
  delete output["subscribe-url"];
  output.mode = "rule";
  output["log-level"] = "info";
  output.dns = {
    nameserver: ["223.5.5.5", "119.29.29.29"],
    "fake-ip-filter": ["+.lan", "*", "+.local", "+.cmpassport.com", "id6.me", "open.e.189.cn", "mdn.open.wo.cn", "opencloud.wostore.cn", "auth.wosms.cn", "+.10099.com.cn", "+.msftconnecttest.com", "+.msftncsi.com", "lancache.steamcontent.com"],
  };
  output["proxy-groups"] = buildProxyGroups();
  output["rule-providers"] = ruleProviders;
  output.rules = rules;
  return output;
}

globalThis.main = main;

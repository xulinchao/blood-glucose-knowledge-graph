import json
import datetime

with open('I:/Project/血糖知识图谱/data/discovered-topics.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

topics = data.get('topics', [])
max_num = 0
for t in topics:
    nid = t.get('id', '').replace('disc-', '')
    if nid.isdigit():
        max_num = max(max_num, int(nid))

base = max_num

new_topics = [
    {
        'id': f'disc-{base+1}',
        'title': '35岁前不控糖，可能错过保护β细胞的黄金窗口',
        'angle': '中国疾控数据显示20-24岁男性糖尿病患病率升至7.42%，40岁以下群体发病率3年激增3倍；ADA与中国糖尿病防治指南均将血糖筛查起始年龄提前至35岁。切入角度：35岁前后肌肉量下降、β细胞老化加速、胰岛素敏感性降低，叠加久坐与高糖饮食，是控糖关键窗口期。',
        'category': '科普',
        'platform': ['抖音', '小红书', 'B站', '知乎'],
        'duration': '60s',
        'heat': '高',
        'heat_source': '央视新闻客户端转载量、权威指南更新、社交讨论',
        'source_urls': ['https://wap.chinanews.com/wap/detail/chs/zw/10683524.shtml', 'https://news.cctv.cn/2025/11/14/ARTIjG3ouxl6aFxxZwCliwOZ251114.shtml'],
        'status': 'discovered',
        'discovered_at': '2026-09-15',
        'evidence_level': 'A',
        'use_as': 'cite_directly',
        'writability_score': 85,
        'authenticity_score': 82,
        'gate': {'passed': True, 'reason': '权威指南+官方数据，可引用'},
        'tags': ['年轻化', '筛查', 'β细胞', '预防']
    },
    {
        'id': f'disc-{base+2}',
        'title': '戴动态血糖仪看奶茶升糖？年轻人为什么疯狂种草CGM',
        'angle': 'CGM正从糖尿病专用设备破圈到普通年轻人。小红书/抖音上年轻人分享佩戴CGM后对奶茶、米饭、荔枝的真实血糖反应；血糖刺客、升糖炸弹等概念流行。欧态M8 MARD值8.106%、鱼跃Anytime5Pro MARD值8.58%成为讨论焦点。',
        'category': '监测',
        'platform': ['小红书', '抖音'],
        'duration': '60s',
        'heat': '高',
        'heat_source': '社交平台笔记浏览量、搜索热度、电商热销',
        'source_urls': ['https://m.thepaper.cn/newsDetail_forward_31075100', 'https://m.36kr.com/p/3549668412862601', 'https://m.jiemian.com/article/14785454.html'],
        'status': 'discovered',
        'discovered_at': '2026-09-15',
        'evidence_level': 'B',
        'use_as': 'verify_before_script',
        'writability_score': 80,
        'authenticity_score': 75,
        'gate': {'passed': True, 'reason': '多方媒体报道，产品参数可核实'},
        'tags': ['CGM', '动态血糖仪', '年轻人', '破圈']
    },
    {
        'id': f'disc-{base+3}',
        'title': '低GI零食是智商税还是真香？山姆vs盒马实测大PK',
        'angle': '低GI零食成为减重社交新宠，但低GI不等于低热量、低碳水，还要看GL和配料表。切入角度：用CGM实测山姆、盒马低GI零食的真实升糖反应，拆解低GI标签背后的商业误导。',
        'category': '饮食',
        'platform': ['小红书', '抖音'],
        'duration': '30s',
        'heat': '高',
        'heat_source': '平台搜索量、博主测评内容、电商推荐',
        'source_urls': ['https://post.m.smzdm.com/p/aww5mrr4/', 'https://m.toutiao.com/group/7534668404993671695/'],
        'status': 'discovered',
        'discovered_at': '2026-09-15',
        'evidence_level': 'C',
        'use_as': 'verify_before_script',
        'writability_score': 78,
        'authenticity_score': 70,
        'gate': {'passed': True, 'reason': '测评类选题，需自行实测验证'},
        'tags': ['低GI', '零食', '测评', '山姆', '盒马']
    },
    {
        'id': f'disc-{base+4}',
        'title': '血糖新标准2026：空腹6.1和餐后7.8，到底怎么判断',
        'angle': '2026年社交平台上血糖新标准帖子刷屏，但权威指标并未频繁变动。切入角度：用北京卫健委等权威来源厘清空腹血糖3.9-6.1、餐后2小时小于7.8、糖尿病前期6.1-7.0/7.8-11.1三条线，辟谣每年更新的误导。',
        'category': '科普',
        'platform': ['小红书', '抖音'],
        'duration': '30s',
        'heat': '中',
        'heat_source': '社交平台转发、评论区讨论、搜索热词',
        'source_urls': ['https://post.m.smzdm.com/p/a4qdzdrk/', 'https://wjw.beijing.gov.cn/bmfw_20143/jkzs/jksh/202604/t20260424_4607974.html'],
        'status': 'discovered',
        'discovered_at': '2026-09-15',
        'evidence_level': 'A',
        'use_as': 'cite_directly',
        'writability_score': 82,
        'authenticity_score': 88,
        'gate': {'passed': True, 'reason': '权威卫健委来源，可引用'},
        'tags': ['血糖标准', '糖尿病前期', '辟谣', '指标']
    },
    {
        'id': f'disc-{base+5}',
        'title': '糖前期不是小病，是逆转血糖的黄金窗口期',
        'angle': '糖尿病前期（空腹6.1-7.0/餐后7.8-11.1）并非不可逆。切入角度：用央视网、北京卫健委权威来源，强调饮食干预+规律运动+体重管理是逆转关键，制造窗口期紧迫感。',
        'category': '生活方式',
        'platform': ['抖音', 'B站', '知乎'],
        'duration': '60s',
        'heat': '中',
        'heat_source': '权威媒体科普、健康栏目推荐、搜索量',
        'source_urls': ['http://jiankang.cctv.com/2026/07/01/ARTIz4OY6xfbMkKTmLmASSAV260701.shtml', 'https://wjw.beijing.gov.cn/bmfw_20143/jkzs/jksh/202604/t20260424_4607974.html'],
        'status': 'discovered',
        'discovered_at': '2026-09-15',
        'evidence_level': 'A',
        'use_as': 'cite_directly',
        'writability_score': 84,
        'authenticity_score': 85,
        'gate': {'passed': True, 'reason': '权威媒体+卫健委来源'},
        'tags': ['糖前期', '逆转', '生活方式', '窗口期']
    },
    {
        'id': f'disc-{base+6}',
        'title': '动态血糖仪怎么选？MARD值、佩戴周期、报警功能全解析',
        'angle': '家用CGM选购核心看MARD值、佩戴周期、数据采集频率。切入角度：横向对比欧态M8（8.106% MARD）、鱼跃Anytime5Pro（8.58% MARD）、万孚（8.66% MARD），教观众看懂硬指标，避免踩坑。',
        'category': '监测',
        'platform': ['B站', '知乎', '什么值得买'],
        'duration': '60s',
        'heat': '中',
        'heat_source': '搜索量、电商热销、科普内容传播',
        'source_urls': ['https://m.jiemian.com/article/14785454.html', 'https://m.bjnews.com.cn/detail/1774419296129161.html'],
        'status': 'discovered',
        'discovered_at': '2026-09-15',
        'evidence_level': 'B',
        'use_as': 'verify_before_script',
        'writability_score': 79,
        'authenticity_score': 76,
        'gate': {'passed': True, 'reason': '产品参数来源可查'},
        'tags': ['CGM', '选购', 'MARD', '横评']
    },
    {
        'id': f'disc-{base+7}',
        'title': '喝水都胖？可能是胰岛素抵抗在作怪，减重5%-10%能改善',
        'angle': '胰岛素抵抗是喝水都胖、三高来袭的隐形推手。切入角度：用人民日报健康版、复旦大学中山医院权威来源，讲清减重5%-10%+增肌+每周150分钟中等强度运动如何改善胰岛素敏感性。',
        'category': '生活方式',
        'platform': ['抖音', '小红书'],
        'duration': '30s',
        'heat': '中',
        'heat_source': '健康栏目、社交平台讨论、科普搜索量',
        'source_urls': ['http://paper.people.com.cn/jksb/pc/attachement/202603/13/67a05291-b63e-4d2e-865f-319589037393.pdf', 'https://shmc.fudan.edu.cn/news/2026/0701/c1893a149659/page.htm'],
        'status': 'discovered',
        'discovered_at': '2026-09-15',
        'evidence_level': 'A',
        'use_as': 'cite_directly',
        'writability_score': 81,
        'authenticity_score': 83,
        'gate': {'passed': True, 'reason': '权威医院+人民日报来源'},
        'tags': ['胰岛素抵抗', '减重', '运动', '代谢']
    },
    {
        'id': f'disc-{base+8}',
        'title': '空腹血糖正常，却突然确诊糖尿病！警惕孤立性餐后高血糖',
        'angle': '很多人只关注空腹血糖，但餐后血糖才是关键。切入角度：用光明网真实案例（空腹正常/餐后21mmol/L）制造震惊感，科普孤立性餐后高血糖概念，提醒只看空腹的误区。',
        'category': '科普',
        'platform': ['抖音', '知乎'],
        'duration': '30s',
        'heat': '中',
        'heat_source': '科普报道、搜索量、评论区讨论',
        'source_urls': ['https://m.gmw.cn/2026-03/18/content_1304380713.htm', 'https://m.youlai.cn/yyk/hnote/A7F1BFmlA5x.html'],
        'status': 'discovered',
        'discovered_at': '2026-09-15',
        'evidence_level': 'B',
        'use_as': 'cite_directly',
        'writability_score': 80,
        'authenticity_score': 78,
        'gate': {'passed': True, 'reason': '权威媒体+医疗平台来源'},
        'tags': ['餐后血糖', '孤立性餐后高血糖', '空腹血糖', '确诊']
    },
    {
        'id': f'disc-{base+9}',
        'title': '低GI国标来了！首部GI测定与标示规范征求意见稿发布',
        'angle': '2026年3月中国疾控中心发布《食物血糖生成指数测定与标示规范》推荐性国家标准征求意见稿，拟规范GI测定与标示。切入角度：解读国标门槛（每份≥7.5g碳水），揭露市场乱象（60款标称低GI产品仅2款能查检测报告），帮观众识别真低GI。',
        'category': '饮食',
        'platform': ['B站', '知乎', '小红书'],
        'duration': '60s',
        'heat': '高',
        'heat_source': '政策发布、媒体报道、社交平台热议',
        'source_urls': ['http://www.chinanutri.cn/tzgg_6537/tzgg_102/202603/t20260318_315598.html', 'https://post.m.smzdm.com/p/aqrm34v7/'],
        'status': 'discovered',
        'discovered_at': '2026-09-15',
        'evidence_level': 'A',
        'use_as': 'cite_directly',
        'writability_score': 83,
        'authenticity_score': 86,
        'gate': {'passed': True, 'reason': '国家标准+权威调查'},
        'tags': ['低GI', '国标', '政策', '市场乱象']
    },
    {
        'id': f'disc-{base+10}',
        'title': '华为要做CGM了？无感血糖监测+AI大模型，血糖管理进入新纪元',
        'angle': '华为HDC2026发布与北京协和医院的高血糖风险评估研究，以及与Dubai Health的糖尿病风险评估合作；欧态科技推出搭载AI助手小欧的生物传感器血糖仪。切入角度：CGM从扎针到无感，从读数到AI对话，技术迭代如何改变血糖管理。',
        'category': '监测',
        'platform': ['抖音', 'B站', '知乎'],
        'duration': '60s',
        'heat': '高',
        'heat_source': '科技媒体报道、社交平台讨论、行业关注',
        'source_urls': ['http://cn.chinadaily.com.cn/a/202606/16/WS6a310667a310d709c2fb86b9.html', 'http://www.js.chinanews.com.cn/news/2026/0520/233700.html'],
        'status': 'discovered',
        'discovered_at': '2026-09-15',
        'evidence_level': 'B',
        'use_as': 'verify_before_script',
        'writability_score': 77,
        'authenticity_score': 74,
        'gate': {'passed': True, 'reason': '多家媒体报道，技术进展可查'},
        'tags': ['华为', 'CGM', 'AI', '无感监测', '科技']
    }
]

topics.extend(new_topics)
data['updated'] = datetime.datetime.now().isoformat()

with open('I:/Project/血糖知识图谱/data/discovered-topics.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'Appended {len(new_topics)} new topics. Total: {len(topics)}')
print('New IDs:', [t['id'] for t in new_topics])

"""
复盘报告服务模块

生成日度复盘报告的核心服务，包含数据聚合、AI 分析、HTML 渲染和 PDF 导出。
"""

from datetime import date
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from app.services.llm_service import LLMService


class ReportService:
    """复盘报告生成服务"""

    def __init__(self):
        """初始化报告服务，加载 Jinja2 模板环境"""
        # 模板目录：backend/templates/
        template_dir = Path(__file__).resolve().parent.parent.parent / "templates"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    async def gather_data(self, report_date: str) -> dict:
        """
        汇总当日数据

        从数据库或外部数据源获取当日市场数据。
        如果数据库未启动或查询失败，则使用模拟数据返回，确保开发阶段可运行。

        Args:
            report_date: 报告日期，格式 YYYY-MM-DD

        Returns:
            dict: 包含当日市场各项指标数据的字典
        """
        logger.info(f"开始汇总 {report_date} 市场数据")

        # 尝试从数据库获取真实数据，失败时回退到模拟数据
        try:
            # TODO: 接入真实数据库查询，当前使用模拟数据
            logger.warning("数据库未就绪，使用模拟数据")
            return self._mock_data(report_date)
        except Exception as e:
            logger.warning(f"数据库查询失败 ({e})，使用模拟数据")
            return self._mock_data(report_date)

    def _mock_data(self, report_date: str) -> dict:
        """
        生成模拟市场数据，用于开发阶段测试

        Args:
            report_date: 报告日期

        Returns:
            dict: 模拟的市场数据
        """
        return {
            "date": report_date,
            "indexes": [
                {
                    "name": "上证指数",
                    "code": "000001.SH",
                    "close": 3150.42,
                    "change_pct": 0.68,
                    "change": 21.35,
                    "status": "up",
                },
                {
                    "name": "深证成指",
                    "code": "399001.SZ",
                    "close": 10450.85,
                    "change_pct": 1.25,
                    "change": 128.63,
                    "status": "up",
                },
                {
                    "name": "创业板指",
                    "code": "399006.SZ",
                    "close": 2050.16,
                    "change_pct": 1.82,
                    "change": 36.58,
                    "status": "up",
                },
            ],
            "market_breadth": {
                "advance": 2850,
                "decline": 1250,
                "total": 4100,
                "advance_pct": 69.5,
                "description": "上涨家数 2850 家，下跌家数 1250 家，市场整体偏强",
            },
            "top_sectors": [
                {"name": "半导体", "change_pct": 3.85, "reason": "国产替代政策利好持续催化"},
                {"name": "人工智能", "change_pct": 3.21, "reason": "大模型应用落地加速"},
                {"name": "消费电子", "change_pct": 2.76, "reason": "Q3 旺季预期带动"},
                {"name": "新能源车", "change_pct": 2.45, "reason": "月度销量数据超预期"},
                {"name": "券商", "change_pct": 2.12, "reason": "市场交投活跃，经纪业务预期改善"},
            ],
            "bottom_sectors": [
                {"name": "煤炭", "change_pct": -1.85, "reason": "煤价下行压力"},
                {"name": "石油石化", "change_pct": -1.42, "reason": "国际油价回落"},
                {"name": "银行", "change_pct": -0.98, "reason": "资金跷跷板效应，成长股吸金"},
                {"name": "公用事业", "change_pct": -0.65, "reason": "防御板块回调"},
                {"name": "钢铁", "change_pct": -0.52, "reason": "需求端偏弱"},
            ],
            "north_flow": {
                "value": 42.85,
                "unit": "亿元",
                "status": "inflow",
                "description": "北向资金当日净买入 42.85 亿元，连续 3 日净流入",
            },
            "limit_up": {
                "count": 85,
                "stocks": ["北方华创", "中科曙光", "科大讯飞", "赛力斯", "宁德时代"],
            },
            "limit_down": {
                "count": 5,
                "stocks": [],
            },
            "main_flow": {
                "value": -56.30,
                "unit": "亿元",
                "status": "outflow",
                "description": "主力资金净流出 56.30 亿元，其中超大单净流入 12.45 亿元",
            },
            "total_volume": 9850,
            "total_volume_unit": "亿元",
        }

    async def generate_ai_text(self, data: dict) -> str:
        """
        构造结构化 Prompt，调用 LLM 生成分析文本

        从 prompts/report_prompt.txt 加载 Prompt 模板，填充数据后调用 LLM。

        Args:
            data: 市场数据字典

        Returns:
            str: AI 生成的复盘分析文本
        """
        # 读取 Prompt 模板
        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "report_prompt.txt"
        if not prompt_path.exists():
            logger.warning("Prompt 模板文件不存在，使用默认模板")
            prompt_template = self._default_prompt_template()
        else:
            prompt_template = prompt_path.read_text(encoding="utf-8")

        # 格式化数据填充到模板中
        prompt = self._format_prompt(prompt_template, data)

        logger.info("调用 LLM 生成复盘分析文本")
        try:
            ai_text = await LLMService.generate(prompt)
            return ai_text
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return self._fallback_ai_text(data)

    def _format_prompt(self, template: str, data: dict) -> str:
        """
        将市场数据格式化填充到 Prompt 模板中

        Args:
            template: Prompt 模板字符串
            data: 市场数据字典

        Returns:
            str: 填充完成后的完整 Prompt
        """
        # 构建大盘数据文本
        index_lines = []
        for idx in data.get("indexes", []):
            arrow = "↑" if idx["status"] == "up" else "↓"
            index_lines.append(
                f"- {idx['name']}（{idx['code']}）: {idx['close']}  {arrow} {idx['change_pct']:+.2f}%"
            )

        # 构建板块数据文本
        top_lines = [
            f"{i+1}. {s['name']} {s['change_pct']:+.2f}%（{s['reason']}）"
            for i, s in enumerate(data.get("top_sectors", []))
        ]
        bottom_lines = [
            f"{i+1}. {s['name']} {s['change_pct']:+.2f}%（{s['reason']}）"
            for i, s in enumerate(data.get("bottom_sectors", []))
        ]

        # 填充模板变量
        fill_values = {
            "date": data.get("date", ""),
            "sh_index": data["indexes"][0]["close"] if data.get("indexes") else "N/A",
            "sh_pct": data["indexes"][0]["change_pct"] if data.get("indexes") else 0,
            "sz_index": data["indexes"][1]["close"] if len(data.get("indexes", [])) > 1 else "N/A",
            "sz_pct": data["indexes"][1]["change_pct"] if len(data.get("indexes", [])) > 1 else 0,
            "cyb_index": data["indexes"][2]["close"] if len(data.get("indexes", [])) > 2 else "N/A",
            "cyb_pct": data["indexes"][2]["change_pct"] if len(data.get("indexes", [])) > 2 else 0,
            "advance": data.get("market_breadth", {}).get("advance", 0),
            "decline": data.get("market_breadth", {}).get("decline", 0),
            "advance_pct": data.get("market_breadth", {}).get("advance_pct", 0),
            "top_sectors": "\n".join(top_lines),
            "bottom_sectors": "\n".join(bottom_lines),
            "north_flow_value": abs(data.get("north_flow", {}).get("value", 0)),
            "north_flow_status": "净买入" if data.get("north_flow", {}).get("status") == "inflow" else "净卖出",
            "north_flow_desc": data.get("north_flow", {}).get("description", ""),
            "limit_up_count": data.get("limit_up", {}).get("count", 0),
            "limit_down_count": data.get("limit_down", {}).get("count", 0),
            "main_flow_value": abs(data.get("main_flow", {}).get("value", 0)),
            "main_flow_status": "净流入" if data.get("main_flow", {}).get("status") == "inflow" else "净流出",
            "main_flow_desc": data.get("main_flow", {}).get("description", ""),
            "total_volume": data.get("total_volume", 0),
        }

        return template.format(**fill_values)

    def _default_prompt_template(self) -> str:
        """
        获取默认 Prompt 模板（当模板文件不存在时使用）

        Returns:
            str: 默认的 Prompt 模板字符串
        """
        return """你是一位专业的A股市场分析师。请根据以下结构化数据，撰写一份专业的复盘日报。

【大盘数据】
- 上证指数: {sh_index}  涨跌幅: {sh_pct:+.2f}%
- 深证成指: {sz_index}  涨跌幅: {sz_pct:+.2f}%
- 创业板指: {cyb_index}  涨跌幅: {cyb_pct:+.2f}%

【涨跌家数】
- 上涨: {advance} 家 ({advance_pct}%)
- 下跌: {decline} 家

【领涨板块 Top 5】
{top_sectors}

【领跌板块 Top 5】
{bottom_sectors}

【北向资金】
{north_flow_desc}

【涨停板统计】
- 涨停: {limit_up_count} 家
- 跌停: {limit_down_count} 家

【主力资金】
{main_flow_desc}

【市场成交额】
{total_volume} 亿元

请从以下五个方面进行分析：
1. 大势研判：分析当日市场整体走势特征，判断当前处于什么阶段（上涨/震荡/调整）
2. 主线板块：梳理当日领涨板块的逻辑，判断是否具备持续性
3. 资金态度：分析北向资金和主力资金动向，判断外资和内资的分歧或共识
4. 风险提示：指出当前市场面临的主要风险因素
5. 次日关注：给出次日需要重点关注的板块和信号

要求：语言专业、数据驱动、观点明确。全文约800-1200字。"""

    def _fallback_ai_text(self, data: dict) -> str:
        """
        当 LLM 调用失败时生成备选分析文本

        Args:
            data: 市场数据字典

        Returns:
            str: 备选分析文本
        """
        sh = data["indexes"][0] if data.get("indexes") else {}
        lines = [
            f"【AI 分析暂不可用 - 基于数据的简要复盘】",
            "",
            f"## 一、大势研判",
            f"当日上证指数收于 {sh.get('close', 'N/A')}，涨跌幅 {sh.get('change_pct', 0):+.2f}%。",
            f"上涨家数 {data.get('market_breadth', {}).get('advance', 0)} 家，占比 {data.get('market_breadth', {}).get('advance_pct', 0)}%，市场整体偏强。",
            "",
            f"## 二、主线板块",
            f"领涨板块：{', '.join([s['name'] for s in data.get('top_sectors', [])])}",
            f"领跌板块：{', '.join([s['name'] for s in data.get('bottom_sectors', [])])}",
            "",
            f"## 三、资金态度",
            f"北向资金：{data.get('north_flow', {}).get('description', '数据暂缺')}",
            f"主力资金：{data.get('main_flow', {}).get('description', '数据暂缺')}",
            "",
            f"## 四、风险提示",
            "市场有风险，投资需谨慎。请结合自身风险承受能力做出决策。",
            "",
            f"## 五、次日关注",
            "建议关注领涨板块的持续性以及北向资金动向。",
        ]
        return "\n".join(lines)

    async def render_html(self, data: dict, ai_text: str) -> str:
        """
        使用 Jinja2 渲染 HTML 报告

        Args:
            data: 市场数据字典
            ai_text: AI 生成的分析文本

        Returns:
            str: 渲染完成的 HTML 字符串
        """
        template = self.env.get_template("report.html")
        html = template.render(
            date=data.get("date", date.today().isoformat()),
            indexes=data.get("indexes", []),
            market_breadth=data.get("market_breadth", {}),
            top_sectors=data.get("top_sectors", []),
            bottom_sectors=data.get("bottom_sectors", []),
            north_flow=data.get("north_flow", {}),
            limit_up=data.get("limit_up", {}),
            limit_down=data.get("limit_down", {}),
            main_flow=data.get("main_flow", {}),
            total_volume=data.get("total_volume", 0),
            total_volume_unit=data.get("total_volume_unit", "亿元"),
            ai_text=ai_text,
        )
        return html

    async def export_pdf(self, html: str) -> bytes:
        """
        使用 Playwright 将 HTML 打印为 PDF

        Args:
            html: HTML 字符串

        Returns:
            bytes: PDF 文件字节流
        """
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.set_content(html, wait_until="networkidle")
                pdf_bytes = await page.pdf(
                    format="A4",
                    margin={"top": "20mm", "bottom": "20mm", "left": "15mm", "right": "15mm"},
                    print_background=True,
                )
                await browser.close()
                logger.info(f"PDF 导出成功，大小: {len(pdf_bytes)} 字节")
                return pdf_bytes
        except ImportError:
            logger.error("Playwright 未安装，请运行: playwright install chromium")
            raise
        except Exception as e:
            logger.error(f"PDF 导出失败: {e}")
            raise

    async def generate_daily(self, report_date: Optional[str] = None) -> dict:
        """
        生成完整复盘报告

        按顺序执行：gather_data → generate_ai_text → render_html，返回报告数据。

        Args:
            report_date: 报告日期，格式 YYYY-MM-DD，默认为当日

        Returns:
            dict: 包含报告各项内容的字典，结构如下：
                - date: 报告日期
                - data: 原始市场数据
                - ai_text: AI 分析文本
                - html: 渲染后的 HTML 内容
                - pdf_bytes: PDF 字节流（可选，需调用 export_pdf）
        """
        if report_date is None:
            report_date = date.today().isoformat()

        logger.info(f"开始生成 {report_date} 复盘报告")

        # 第一步：汇总数据
        data = await self.gather_data(report_date)

        # 第二步：AI 分析
        ai_text = await self.generate_ai_text(data)

        # 第三步：渲染 HTML
        html = await self.render_html(data, ai_text)

        result = {
            "date": report_date,
            "data": data,
            "ai_text": ai_text,
            "html": html,
        }

        logger.info(f"{report_date} 复盘报告生成完成")
        return result

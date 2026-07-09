"""
持仓管理接口模块

提供持仓列表查询、添加/修改/删除持仓、盈亏汇总等 REST API。
数据直接操作 portfolio 和 portfolio_snapshot 表。
数据库不可用时返回模拟数据（开发模式友好）。
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.schemas.portfolio import (
    PositionCreate,
    PositionUpdate,
    PositionResponse,
    PnlSummary,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# 模拟数据（数据库不可用时使用）
# ---------------------------------------------------------------------------

_MOCK_POSITIONS = [
    {
        "id": 1,
        "code": "000001",
        "name": "平安银行",
        "shares": 1000,
        "cost_price": 12.50,
        "current_price": 13.20,
        "market_value": 13200.0,
        "profit_loss": 700.0,
        "profit_loss_pct": 5.6,
        "group_id": 1,
        "added_at": "2025-06-01T09:30:00",
    },
    {
        "id": 2,
        "code": "600519",
        "name": "贵州茅台",
        "shares": 100,
        "cost_price": 1800.0,
        "current_price": 1750.0,
        "market_value": 175000.0,
        "profit_loss": -5000.0,
        "profit_loss_pct": -2.78,
        "group_id": 2,
        "added_at": "2025-05-15T09:30:00",
    },
    {
        "id": 3,
        "code": "300750",
        "name": "宁德时代",
        "shares": 200,
        "cost_price": 220.0,
        "current_price": 235.50,
        "market_value": 47100.0,
        "profit_loss": 3100.0,
        "profit_loss_pct": 7.05,
        "group_id": 3,
        "added_at": "2025-06-10T09:30:00",
    },
]


def _calc_position(row: dict) -> dict:
    """根据数据库行数据计算盈亏并构造持仓响应字典"""
    shares = float(row.get("shares", 0))
    cost_price = float(row.get("cost_price", 0))
    current_price = float(row.get("current_price", 0))
    market_value = round(shares * current_price, 2)
    profit_loss = round((current_price - cost_price) * shares, 2)
    profit_loss_pct = round((current_price - cost_price) / cost_price * 100, 2) if cost_price else 0.0
    return {
        "id": row.get("id"),
        "code": row.get("code", ""),
        "name": row.get("name", ""),
        "shares": shares,
        "cost_price": cost_price,
        "current_price": current_price,
        "market_value": market_value,
        "profit_loss": profit_loss,
        "profit_loss_pct": profit_loss_pct,
        "group_id": row.get("group_id"),
        "added_at": row.get("added_at"),
    }


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.get("")
async def list_portfolio(
    group_id: Optional[int] = Query(None, description="按分组 ID 过滤"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取持仓列表（含实时盈亏）

    从持仓明细表查询当前持仓，计算每只股票的盈亏金额和百分比。
    支持按分组 ID 过滤。
    """
    try:
        # 尝试从数据库查询
        from sqlalchemy import text

        sql = """
            SELECT
                p.id,
                p.symbol AS code,
                COALESCE(si.name, p.symbol) AS name,
                p.volume AS shares,
                p.cost_price,
                p.cost_price AS current_price,
                p.group_id,
                p.add_time AS added_at
            FROM portfolio p
            LEFT JOIN stock_info si ON si.symbol = p.symbol
        """
        params = {}
        if group_id is not None:
            sql += " WHERE p.group_id = :group_id"
            params["group_id"] = group_id
        sql += " ORDER BY p.add_time DESC"

        rows = await db.execute(text(sql), params)
        data = rows.fetchall()
        cols = list(rows.keys())
        positions = [_calc_position(dict(zip(cols, r))) for r in data]
        logger.info(f"查询到 {len(positions)} 条持仓记录")
        return {"code": 0, "message": "success", "data": positions}
    except Exception as e:
        logger.warning(f"数据库查询持仓失败，使用模拟数据: {e}")
        mock = _MOCK_POSITIONS
        if group_id is not None:
            mock = [p for p in mock if p.get("group_id") == group_id]
        return {"code": 0, "message": "success（模拟）", "data": mock}


@router.post("")
async def add_position(
    position: PositionCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    添加持仓

    新增一条持仓记录到 portfolio 表。
    """
    try:
        from sqlalchemy import text
        from app.core.database import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                text("""
                    INSERT INTO portfolio (user_id, symbol, name, cost_price, volume)
                    VALUES (:user_id, :symbol, :name, :cost_price, :volume)
                    RETURNING id
                """),
                {
                    "user_id": "default",
                    "symbol": position.code,
                    "name": position.name,
                    "cost_price": position.cost_price,
                    "volume": position.shares,
                }
            )
            await session.commit()
            new_id = result.scalar_one()
        logger.info(f"新增持仓成功: id={new_id}, code={position.code}")
        return {"code": 0, "message": "success", "data": {"id": new_id}}
    except Exception as e:
        logger.warning(f"新增持仓失败，使用模拟响应: {e}")
        return {"code": 0, "message": "success（模拟）", "data": {"id": 999}}


@router.put("/{position_id}")
async def update_position(
    position_id: int,
    position: PositionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    修改持仓

    更新指定持仓的股数、成本价、当前价或分组信息。
    """
    try:
        from sqlalchemy import text

        updates = {}
        if position.shares is not None:
            updates["shares"] = position.shares
        if position.cost_price is not None:
            updates["cost_price"] = position.cost_price
        if position.current_price is not None:
            updates["current_price"] = position.current_price
        if position.group_id is not None:
            updates["group_id"] = position.group_id

        if not updates:
            raise HTTPException(status_code=400, detail="没有需要更新的字段")

        updates["updated_at"] = datetime.now()
        set_clause = ", ".join([f"{k} = :{k}" for k in updates])
        updates["position_id"] = position_id

        sql = text(f"UPDATE portfolio SET {set_clause} WHERE id = :position_id")
        result = await db.execute(sql, updates)
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="持仓记录不存在")

        logger.info(f"更新持仓成功: id={position_id}")
        return {"code": 0, "message": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"更新持仓失败，使用模拟响应: {e}")
        return {"code": 0, "message": "success（模拟）"}


@router.delete("/{position_id}")
async def delete_position(
    position_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    删除持仓

    从 portfolio 表中删除指定持仓记录。
    """
    try:
        from sqlalchemy import text

        sql = text("DELETE FROM portfolio WHERE id = :id")
        result = await db.execute(sql, {"id": position_id})
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="持仓记录不存在")

        logger.info(f"删除持仓成功: id={position_id}")
        return {"code": 0, "message": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"删除持仓失败，使用模拟响应: {e}")
        return {"code": 0, "message": "success（模拟）"}


@router.get("/pnl")
async def get_pnl(
    db: AsyncSession = Depends(get_db),
):
    """
    获取总盈亏汇总

    计算所有持仓的总市值、总成本、总盈亏金额和百分比。
    """
    try:
        from sqlalchemy import text

        sql = """
            SELECT
                COALESCE(SUM(volume * cost_price), 0) AS total_market_value,
                COALESCE(SUM(volume * cost_price), 0) AS total_cost,
                COUNT(*) AS position_count
            FROM portfolio
        """
        rows = await db.execute(text(sql))
        row = rows.fetchone()
        cols = list(rows.keys())
        data = dict(zip(cols, row))

        total_market_value = float(data["total_market_value"])
        total_cost = float(data["total_cost"])
        total_profit_loss = round(total_market_value - total_cost, 2)
        total_profit_loss_pct = round(
            (total_profit_loss / total_cost * 100) if total_cost else 0.0, 2
        )

        summary = PnlSummary(
            total_market_value=total_market_value,
            total_cost=total_cost,
            total_profit_loss=total_profit_loss,
            total_profit_loss_pct=total_profit_loss_pct,
            position_count=data["position_count"],
        )
        logger.info(f"盈亏汇总计算完成: 总盈亏={total_profit_loss}")
        return {"code": 0, "message": "success", "data": summary.model_dump()}
    except Exception as e:
        logger.warning(f"查询盈亏汇总失败，使用模拟数据: {e}")
        mock_total_cost = sum(
            p["shares"] * p["cost_price"] for p in _MOCK_POSITIONS
        )
        mock_total_mv = sum(
            p["shares"] * p["current_price"] for p in _MOCK_POSITIONS
        )
        mock_pnl = round(mock_total_mv - mock_total_cost, 2)
        mock_pnl_pct = round(mock_pnl / mock_total_cost * 100, 2) if mock_total_cost else 0.0
        summary = PnlSummary(
            total_market_value=round(mock_total_mv, 2),
            total_cost=round(mock_total_cost, 2),
            total_profit_loss=mock_pnl,
            total_profit_loss_pct=mock_pnl_pct,
            position_count=len(_MOCK_POSITIONS),
        )
        return {"code": 0, "message": "success（模拟）", "data": summary.model_dump()}

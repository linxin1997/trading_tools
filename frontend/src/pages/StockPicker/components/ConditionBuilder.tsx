import { useState, useEffect } from 'react'
import { Card, Select, InputNumber, Button, Space, Slider, Switch, Typography, Tag } from 'antd'
import { PlusOutlined, DeleteOutlined, MinusCircleOutlined } from '@ant-design/icons'
import { getFactors } from '../../../services/api'
import type { Factor, ConditionGroup, Condition, Operator } from '../types'
import { OPERATOR_LABELS } from '../types'

const { Text, Title } = Typography

/** 条件构建器属性 */
interface ConditionBuilderProps {
  onScreen: (groups: ConditionGroup[], weights: Record<string, number>, compareMode: boolean) => void
  loading?: boolean
}

/** 生成唯一 ID */
let idCounter = 0
function genId(): string {
  idCounter += 1
  return `c_${idCounter}_${Date.now()}`
}

/**
 * 条件构建器组件
 * 支持 And/Or 逻辑组、因子选择、运算符、值输入、权重配置
 */
function ConditionBuilder({ onScreen, loading = false }: ConditionBuilderProps) {
  const [factors, setFactors] = useState<Factor[]>([])
  const [factorsLoading, setFactorsLoading] = useState(false)
  const [groups, setGroups] = useState<ConditionGroup[]>([
    { id: genId(), logic: 'AND', conditions: [] },
  ])
  const [weights, setWeights] = useState<Record<string, number>>({})
  const [compareMode, setCompareMode] = useState(false)

  /** 初始化加载因子列表 */
  useEffect(() => {
    setFactorsLoading(true)
    getFactors()
      .then((data) => {
        setFactors(data || [])
        // 初始化权重
        const initialWeights: Record<string, number> = {}
        ;(data || []).forEach((f) => { initialWeights[f.key] = 50 })
        setWeights(initialWeights)
      })
      .catch(() => {
        // 加载失败时使用默认因子
        const fallback: Factor[] = [
          { key: 'maAlignment', label: '均线排列', type: 'enum', options: [{ label: '多头排列', value: 'bullish' }, { label: '空头排列', value: 'bearish' }] },
          { key: 'macdGoldenCross', label: 'MACD金叉', type: 'boolean' },
          { key: 'kdjSignal', label: 'KDJ信号', type: 'enum', options: [{ label: '金叉', value: 'goldenCross' }, { label: '死叉', value: 'deadCross' }] },
          { key: 'volumeRatio', label: '量比', type: 'number' },
          { key: 'turnoverRate', label: '换手率', type: 'number' },
          { key: 'peRatio', label: '市盈率', type: 'number' },
          { key: 'pbRatio', label: '市净率', type: 'number' },
          { key: 'roe', label: 'ROE', type: 'number' },
          { key: 'marketCap', label: '总市值', type: 'number' },
        ]
        setFactors(fallback)
        const initialWeights: Record<string, number> = {}
        fallback.forEach((f) => { initialWeights[f.key] = 50 })
        setWeights(initialWeights)
      })
      .finally(() => setFactorsLoading(false))
  }, [])

  /** 切换逻辑组运算符 */
  function toggleLogic(groupId: string) {
    setGroups((prev) =>
      prev.map((g) =>
        g.id === groupId ? { ...g, logic: g.logic === 'AND' ? 'OR' : 'AND' } : g,
      ),
    )
  }

  /** 添加空条件到指定组 */
  function addCondition(groupId: string) {
    const defaultFactor = factors[0]
    if (!defaultFactor) return
    const newCondition: Condition = {
      id: genId(),
      factorKey: defaultFactor.key,
      operator: 'equals',
      value: defaultFactor.type === 'boolean' ? true : '',
    }
    setGroups((prev) =>
      prev.map((g) =>
        g.id === groupId ? { ...g, conditions: [...g.conditions, newCondition] } : g,
      ),
    )
  }

  /** 删除条件 */
  function removeCondition(groupId: string, conditionId: string) {
    setGroups((prev) =>
      prev.map((g) =>
        g.id === groupId
          ? { ...g, conditions: g.conditions.filter((c) => c.id !== conditionId) }
          : g,
      ),
    )
  }

  /** 更新条件字段 */
  function updateCondition(groupId: string, conditionId: string, patch: Partial<Condition>) {
    setGroups((prev) =>
      prev.map((g) =>
        g.id === groupId
          ? {
              ...g,
              conditions: g.conditions.map((c) =>
                c.id === conditionId ? { ...c, ...patch } : c,
              ),
            }
          : g,
      ),
    )
  }

  /** 添加逻辑组 */
  function addGroup() {
    setGroups((prev) => [...prev, { id: genId(), logic: 'AND', conditions: [] }])
  }

  /** 删除逻辑组 */
  function removeGroup(groupId: string) {
    if (groups.length <= 1) return
    setGroups((prev) => prev.filter((g) => g.id !== groupId))
  }

  /** 获取因子对象 */
  function getFactor(key: string): Factor | undefined {
    return factors.find((f) => f.key === key)
  }

  /** 获取因子的运算符列表 */
  function getOperatorsForFactor(factor?: Factor): Operator[] {
    if (!factor) return ['equals']
    if (factor.type === 'boolean') return ['equals', 'notEquals']
    if (factor.type === 'enum') return ['equals', 'notEquals']
    return ['equals', 'greaterThan', 'lessThan', 'gte', 'lte', 'between']
  }

  /** 触发筛选 */
  function handleScreen() {
    onScreen(groups, weights, compareMode)
  }

  /** 是否有至少一个条件 */
  const hasAnyCondition = groups.some((g) => g.conditions.length > 0)

  return (
    <Card
      title={
        <Space>
          <Title level={5} style={{ margin: 0 }}>条件构建</Title>
          {factorsLoading && <Text type="secondary">加载因子中...</Text>}
        </Space>
      }
    >
      {/* 条件组列表 */}
      {groups.map((group, groupIdx) => (
        <div
          key={group.id}
          style={{
            marginBottom: 16,
            padding: 12,
            border: '1px solid #f0f0f0',
            borderRadius: 6,
            background: '#fafafa',
          }}
        >
          {/* 组头：逻辑切换 + 删除组 */}
          <Space style={{ marginBottom: 8 }}>
            <Tag
              color="blue"
              style={{ cursor: 'pointer' }}
              onClick={() => toggleLogic(group.id)}
            >
              {group.logic}
            </Tag>
            <Text type="secondary">逻辑组 {groupIdx + 1}</Text>
            {groups.length > 1 && (
              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => removeGroup(group.id)}
              />
            )}
          </Space>

          {/* 条件列表 */}
          {group.conditions.map((cond) => {
            const factor = getFactor(cond.factorKey)
            const ops = getOperatorsForFactor(factor)
            return (
              <Space key={cond.id} style={{ marginBottom: 8, width: '100%' }} align="baseline">
                {/* 因子选择 */}
                <Select
                  value={cond.factorKey}
                  onChange={(val) => updateCondition(group.id, cond.id, { factorKey: val })}
                  style={{ width: 140 }}
                  options={factors.map((f) => ({ label: f.label, value: f.key }))}
                />

                {/* 运算符选择 */}
                <Select
                  value={cond.operator}
                  onChange={(val) => updateCondition(group.id, cond.id, { operator: val as Operator })}
                  style={{ width: 100 }}
                  options={ops.map((op) => ({ label: OPERATOR_LABELS[op], value: op }))}
                />

                {/* 值输入 */}
                {factor?.type === 'boolean' ? (
                  <Select
                    value={String(cond.value)}
                    onChange={(val) => updateCondition(group.id, cond.id, { value: val === 'true' })}
                    style={{ width: 80 }}
                    options={[
                      { label: '是', value: 'true' },
                      { label: '否', value: 'false' },
                    ]}
                  />
                ) : factor?.type === 'enum' ? (
                  <Select
                    value={cond.value as string}
                    onChange={(val) => updateCondition(group.id, cond.id, { value: val })}
                    style={{ width: 120 }}
                    options={factor.options || []}
                  />
                ) : (
                  <InputNumber
                    value={cond.value as number}
                    onChange={(val) => updateCondition(group.id, cond.id, { value: val ?? 0 })}
                    style={{ width: 100 }}
                    placeholder="数值"
                  />
                )}

                {/* 介于的第二个值 */}
                {cond.operator === 'between' && (
                  <>
                    <Text>~</Text>
                    <InputNumber
                      value={cond.valueEnd as number}
                      onChange={(val) => updateCondition(group.id, cond.id, { valueEnd: val ?? 0 })}
                      style={{ width: 100 }}
                      placeholder="最大值"
                    />
                  </>
                )}

                {/* 删除条件按钮 */}
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<MinusCircleOutlined />}
                  onClick={() => removeCondition(group.id, cond.id)}
                />
              </Space>
            )
          })}

          {/* 添加条件按钮 */}
          <Button
            type="dashed"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => addCondition(group.id)}
          >
            添加条件
          </Button>
        </div>
      ))}

      {/* 添加逻辑组按钮 */}
      <Button type="dashed" onClick={addGroup} style={{ marginBottom: 16 }}>
        + 添加逻辑组
      </Button>

      {/* 权重配置 */}
      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ display: 'block', marginBottom: 8 }}>权重配置</Text>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
          {factors.map((f) => (
            <div key={f.key} style={{ width: 180 }}>
              <Text style={{ fontSize: 12 }}>{f.label}</Text>
              <Slider
                min={0}
                max={100}
                value={weights[f.key] ?? 50}
                onChange={(val) => setWeights((prev) => ({ ...prev, [f.key]: val }))}
                tooltip={{ formatter: (val) => `${val}%` }}
              />
            </div>
          ))}
        </div>
      </div>

      {/* 操作按钮区 */}
      <Space>
        <Button type="primary" onClick={handleScreen} loading={loading} disabled={!hasAnyCondition}>
          筛选
        </Button>
        <Space>
          <Text type="secondary">对比模式</Text>
          <Switch checked={compareMode} onChange={setCompareMode} />
        </Space>
      </Space>
    </Card>
  )
}

export default ConditionBuilder

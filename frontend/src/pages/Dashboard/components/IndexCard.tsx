import { Card, Statistic, Row, Col } from 'antd'
import { CaretUpOutlined, CaretDownOutlined } from '@ant-design/icons'
import useMarketStore from '../../../stores/useMarketStore'

/** A 股涨跌颜色配置 */
const COLORS = {
  up: '#f5222d',
  down: '#52c41a',
  flat: '#d9d9d9',
}

/**
 * 获取涨跌幅对应的颜色和图标
 * @param value - 涨跌幅数值
 * @returns 颜色值和图标元素
 */
function getChangeInfo(value: number) {
  if (value > 0) {
    return { color: COLORS.up, icon: <CaretUpOutlined /> }
  }
  if (value < 0) {
    return { color: COLORS.down, icon: <CaretDownOutlined /> }
  }
  return { color: COLORS.flat, icon: null }
}

/**
 * 指数卡片组件
 * 显示大盘指数名称、当前点位、涨跌幅，涨为红色跌为绿色
 */
function IndexCard() {
  const indices = useMarketStore((state) => state.indices)

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      {indices.length === 0 ? (
        // 无数据时显示占位卡片
        [['上证指数', '000001.SH'], ['深证成指', '399001.SZ'], ['创业板指', '399006.SZ'], ['科创50', '000688.SH']].map(
          ([name, code]) => (
            <Col span={6} key={code}>
              <Card size="small" loading={true}>
                <Statistic title={name} value="--" />
              </Card>
            </Col>
          ),
        )
      ) : (
        indices.slice(0, 4).map((index) => {
          const { color, icon } = getChangeInfo(index.changePercent)
          const sign = index.changePercent >= 0 ? '+' : ''
          return (
            <Col span={6} key={index.code}>
              <Card size="small" hoverable>
                <Statistic
                  title={index.name}
                  value={index.point}
                  precision={2}
                  suffix={
                    <span style={{ color, fontSize: 14, fontWeight: 500 }}>
                      {icon} {sign}
                      {index.changePercent.toFixed(2)}%
                    </span>
                  }
                  valueStyle={{ fontSize: 22, fontWeight: 600 }}
                />
              </Card>
            </Col>
          )
        })
      )}
    </Row>
  )
}

export default IndexCard

# 深度登记 药房近效期批次调拨与可用量

- 规模：中型
- 使用者与工作流：连锁药房库存核对员，汇集批号库存与调拨申请，按可用有效期安排门店补货。
- 核心规则：FEFO仅分配到店后剩余有效期满足需求的库存；冻结量先扣，拆包需整包装，召回批不得调拨。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 库存接收 | 运行库存接收并复核证据 | `POST /api/m1`；`/work/1` | `app/modules/m1_receiving/rules.py` | `tests/test_m1.py` |
| M2 批号裁决 | 运行批号裁决并复核证据 | `POST /api/m2`；`/work/2` | `app/modules/m2_lots/rules.py` | `tests/test_m2.py` |
| M3 效期分层 | 运行效期分层并复核证据 | `POST /api/m3`；`/work/3` | `app/modules/m3_expiry/rules.py` | `tests/test_m3.py` |
| M4 需求净额 | 运行需求净额并复核证据 | `POST /api/m4`；`/work/4` | `app/modules/m4_demand/rules.py` | `tests/test_m4.py` |
| M5 调拨分配 | 运行调拨分配并复核证据 | `POST /api/m5`；`/work/5` | `app/modules/m5_allocation/rules.py` | `tests/test_m5.py` |
| M6 收发对账 | 运行收发对账并复核证据 | `POST /api/m6`；`/work/6` | `app/modules/m6_reconcile/rules.py` | `tests/test_m6.py` |
| M7 方案复核 | 运行方案复核并复核证据 | `POST /api/m7`；`/work/7` | `app/modules/m7_approval/rules.py` | `tests/test_m7.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现会怎样 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-02 | BOM | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m1_receiving/rules.py` | `tests/test_m1.py::test_bom` |
| TRAP-05 | 列数不齐 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m1_receiving/rules.py` | `tests/test_m1.py::test_bad_columns` |
| TRAP-07 | 空值数量 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m2_lots/rules.py` | `tests/test_m2.py::test_missing_quantity` |
| TRAP-08 | 药品编码前导零 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m2_lots/rules.py` | `tests/test_m2.py::test_sku_leading_zero` |
| TRAP-14 | 同单冲突 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m2_lots/rules.py` | `tests/test_m2.py::test_conflict_not_override` |
| TRAP-19 | 召回优先 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m2_lots/rules.py` | `tests/test_m2.py::test_recall_dominates` |
| TRAP-23 | 效期端点 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m3_expiry/rules.py` | `tests/test_m3.py::test_expired_isolated` |
| TRAP-26 | 陈旧复核 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m7_approval/rules.py` | `tests/test_m7.py::test_review_api_stale` |
| TRAP-31 | 同批号补录修订 | 用新文件覆盖旧方案，原复核与占库依据丢失 | 修订链不可变版本，关联替代并切换当前方案，旧版本完整可查 | `app/revision.py`、`app/store.py` | `tests/test_revision.py::test_original_run_and_decision_remain_queryable` |
| TRAP-32 | 同修订号异值/修订倒退 | 按文件顺序盲目覆盖 | 同修订异值 CONFLICT 拒绝；倒退 REV_STALE 隔离且不倒扣，两遍扫描与行序无关 | `app/revision.py::adjudicate_record` | `tests/test_revision.py::test_same_revision_different_value_rejected` |
| TRAP-33 | 旧方案未发占库 | 新方案按最新库存重复占用 | 按批号汇总未发占用，分配前从最新可调拨预留，失效占用显式登记 | `app/revision.py::reserve_holds` | `tests/test_revision.py::test_revision_takes_latest_stock_and_inherits_hold` |
| TRAP-34 | 修订重试 | 中断续跑重复生成版本、重复占库 | run内容哈希复用 + idempotency_key 双重幂等，链序号唯一约束 | `app/store.py::save_revision` | `tests/test_revision.py::test_idempotent_retry_does_not_duplicate_hold` |

## 对账规则

输入记录 = 采信记录 + 隔离记录 + 相同行重复。重复表头与空行单独记数。业务合计按阶段中的守恒或差值列复核。运行清单有原文SHA256、规则版本与耗时；相同规则版本下同文重复提交复用批次。

## 已知不覆盖

部署为本地单用户工具，不连接外部上游系统。CSV单文件5MB及一万条业务记录上限；不推断未提供的未知数据。修订机制不改动效期判定与整包装取整算法，不执行实际物流发货，因此历史方案调拨量全部视为未发占用。

## 修订替代版本

`app/revision.py` 承担链指纹、占用汇总、预留与修订号裁决；`app/store.py` 在 runs 之外维护 chains（当前执行方案指针）与 idempotency（重试键）两张表。入口 `POST /api/revision`，链查询 `GET /api/chains/<id>`，切换 `POST /api/runs/<id>/activate`。M7 页面按需求单与批号两个维度核对原量、新量、未发占用与可用差额。

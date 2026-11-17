from pathlib import Path
RULE_VERSION = "2026.11.18.2"
TITLE = '药房近效期批次调拨与可用量'
SHORT = 'pharma-fefo'
MODULES = ['库存接收', '批号裁决', '效期分层', '需求净额', '调拨分配', '收发对账', '方案复核']
HEADERS = ['record', 'kind', 'sku', 'lot', 'qty', 'frozen', 'pack', 'expiry', 'store', 'min_days', 'arrival', 'version', 'status']
SAMPLE = Path(__file__).resolve().parent.parent / "sample_data" / "operations.csv"
LIMIT = 10000

REASONS = {"COLUMNS":"列数不符", "HEADER":"字段缺失", "MISSING":"必填值为空", "NUMBER":"数值无效", "RANGE":"超出范围", "DUPLICATE":"相同行重复", "CONFLICT":"同键数值冲突", "VERSION":"版本冲突", "REV_STALE":"修订号倒退", "REV_CONFLICT":"同修订号异值", "CHAIN":"修订链不存在", "HOLD":"占库承接异常", "EMPTY":"输入为空", "STRUCTURE":"文件结构错误"}
def isolate(ctx, row, code, detail):
    ctx['quarantine'].append({**row, '原因码': code, '原因': detail})

# -*- coding: utf-8 -*-
"""一键导入"青年驿站"目录下的所有 Excel 数据到数据库。

会自动扫描项目根目录下的 *.xlsx 文件（兼容工作地图导出格式与标准模板），
按 名称+地址 去重，已存在则更新，不存在则新增。

用法：
    python seed_from_excel.py
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import Station, db
from utils import amap_geocode, parse_city_district, read_stations_from_excel

# 扫描项目根目录（即 web/ 上一级）下所有 .xlsx
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def discover_targets():
    files = sorted(glob.glob(os.path.join(ROOT, "*.xlsx")))
    # 排除临时文件
    return [f for f in files if not os.path.basename(f).startswith("~$")]


def main():
    app = create_app()
    with app.app_context():
        amap_key = app.config.get("AMAP_WEB_KEY")
        if not amap_key:
            print("[WARN] 未配置 AMAP_WEB_KEY，将跳过自动地理编码（驿站可在管理后台单条编辑时再补全）")

        targets = discover_targets()
        if not targets:
            print(f"[ERROR] 在 {ROOT} 下未找到任何 .xlsx 文件")
            return

        print(f"[SCAN] 发现 {len(targets)} 个 Excel 文件:")
        for f in targets:
            print(f"   - {os.path.basename(f)}")
        print()

        total_added = total_updated = total_skipped = 0
        per_file_stats = []
        for f in targets:
            print(f"[READ] {os.path.basename(f)}")
            try:
                with open(f, "rb") as fh:
                    records = read_stations_from_excel(fh)
            except Exception as e:
                print(f"  [SKIP] 解析失败: {e}")
                continue
            print(f"  - 解析 {len(records)} 条")

            f_added = f_updated = f_skipped = 0
            for r in records:
                if not r["name"] or not r["address"]:
                    f_skipped += 1
                    continue
                # 自动补全城市/区
                if not r["city"] or not r["district"]:
                    p, c, d = parse_city_district(r["address"])
                    r["city"] = r["city"] or c
                    r["district"] = r["district"] or d
                # 同名+同地址 视为已存在
                existing = Station.query.filter_by(name=r["name"], address=r["address"]).first()
                target = existing or Station()
                target.name = r["name"]
                target.address = r["address"]
                target.city = r["city"]
                target.district = r["district"]
                target.guide_html = r["guide_html"] or target.guide_html
                target.remark = r["remark"] or target.remark
                target.folder = r["folder"] or target.folder
                target.location_code = r["location_code"] or target.location_code
                if amap_key and (not target.lng or not target.lat):
                    xy = amap_geocode(target.address, target.city, amap_key)
                    if xy:
                        target.lng, target.lat = xy
                if existing:
                    f_updated += 1
                else:
                    db.session.add(target)
                    f_added += 1
            db.session.commit()
            print(f"  - 新增 {f_added}，更新 {f_updated}，跳过 {f_skipped}")
            per_file_stats.append((os.path.basename(f), f_added, f_updated, f_skipped))
            total_added += f_added
            total_updated += f_updated
            total_skipped += f_skipped

        # 汇总
        print("\n" + "=" * 60)
        print("[SUMMARY] 各文件入库情况:")
        for n, a, u, s in per_file_stats:
            print(f"  {n[:50]:52s}  +{a:<3d}  ~{u:<3d}  -{s}")
        print("=" * 60)
        print(f"[DONE] 共新增 {total_added}，更新 {total_updated}，跳过 {total_skipped}")

        # 各城市统计
        from sqlalchemy import func
        city_rows = db.session.query(Station.city, func.count(Station.id)).group_by(Station.city).all()
        print("\n[CITIES] 数据库当前各城市驿站数：")
        for c, n in sorted(city_rows, key=lambda x: -x[1]):
            print(f"  {c or '未知':10s}  {n} 条")


if __name__ == "__main__":
    main()

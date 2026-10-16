"""运行全部课程评分器；无网络、不读取真实接口配置。"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

GRADERS = ('grade.py', 'grade02.py', 'grade03.py', 'grade04.py', 'grade04_agent.py',
           'grade05.py', 'grade05_controls.py', 'grade06.py', 'grade06_events.py', 'grade07.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, help='可选：保存机器可读的测试结果')
    args = parser.parse_args()
    root = Path(__file__).parent
    results = []
    for grader in GRADERS:
        try:
            result = subprocess.run([sys.executable, '-X', 'utf8', grader], cwd=root,
                                    capture_output=True, text=True, encoding='utf-8', timeout=40)
            summaries = re.findall(r'(?:接线题)?总分：[0-9]+/[0-9]+', result.stdout)
            summary = summaries[-1] if summaries else '无评分结果'
            passed = result.returncode == 0 and summary.endswith('100/100')
            results.append({'grader': grader, 'passed': passed, 'exit_code': result.returncode, 'summary': summary})
            print(f"{'PASS' if passed else 'FAIL'} {grader}: {summary}")
            if not passed:
                print(result.stdout + result.stderr)
        except subprocess.TimeoutExpired:
            results.append({'grader': grader, 'passed': False, 'summary': '评分超时'})
            print('FAIL', grader, '评分超时')
    report = {'scope': 'offline-course-graders-and-local-mcp', 'all_passed': all(r['passed'] for r in results), 'results': results}
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"通过 {sum(r['passed'] for r in results)}/{len(results)} 个评分入口")
    return 0 if report['all_passed'] else 1


if __name__ == '__main__':
    sys.exit(main())

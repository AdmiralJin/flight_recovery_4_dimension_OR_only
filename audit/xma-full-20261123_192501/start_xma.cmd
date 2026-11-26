@echo off
chcp 65001 >nul
title XMA HiGHS first solution - FULL
cd /d "G:\jzm\project\flight_recovery\.public_benchmarks\xma-full-20261123_192501\source"
"D:\ProgramData\Anaconda_envs\envs\xma_highs\python.exe" -u "G:\jzm\project\flight_recovery\.public_benchmarks\xma-full-20261123_192501\source\scripts\xma_first_solution.py" run "G:\jzm\project\flight_recovery\.public_benchmarks\xma-full-20261123_192501"

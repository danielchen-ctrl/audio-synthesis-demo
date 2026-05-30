@echo off
title V2-Frontend
:: 从 run\ 进入 frontend 目录
cd /d "%~dp0..\frontend"
npm run dev

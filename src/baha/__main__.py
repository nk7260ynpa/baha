"""baha 套件的 CLI 進入點。

允許使用 ``python -m baha`` 呼叫 pipeline.main()，執行一次抓取並寫入資料庫。
"""

from baha.pipeline import main


if __name__ == "__main__":
    main()

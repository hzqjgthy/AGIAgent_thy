rm -rf .git

第一次提交：

git init

git config --global user.email "274579....@qq.com" 

git config --global user.name "hzqjgthy"

git add . 

git commit -m "11111"  

git remote add origin https://github.com/hzqjgthy/FPS.git


git push -u origin main


后续提交：

git add .

git commit -m "提交说明"

git push





export https_proxy=http://127.0.0.1:7890                 
export http_proxy=http://127.0.0.1:7890
# query_pkg_deps

## 概要
こじまみつひろさんのget_depends.pyを使って作成したdepends.sql3を利用し、指定したパッケージに依存しているパッケージを列挙します。  
[第29回共有ライブラリと依存関係［1］](https://gihyo.jp/lifestyle/serial/01/ganshiki-soushi-2/0029)

## 使い方
同じディレクトリにget_depends.pyで作成したdepends.sql3を置いてください。
```
./query_pkg_deps.py <package_name>
```

## 例

```
./query_pkg_deps.py liblxqt
lxqt_about
lxqt_admin
lxqt_config
lxqt_globalkeys
lxqt_notificationd
lxqt_openssh_askpass
lxqt_panel
lxqt_policykit
lxqt_powermanagement
lxqt_runner
lxqt_session
lxqt_sudo
qps
uim_toolbar_qt6_lxqtwidget
```

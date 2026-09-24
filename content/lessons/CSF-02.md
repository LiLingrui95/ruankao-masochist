## 顺序执行：只看这一步发生了什么

先修自查：`total = 6` 与 `print(total)` 的区别是什么？如果不确定，可以返回第 1 单元的“赋值和输出”。

程序的状态会随着执行变化。赋值保存当前计算结果，并不会建立一个自动更新的数学公式。

```python
quantity = 3
total = quantity * 12
quantity = 4
print(total)
```

输出是 **36**。第二行执行时 quantity 为 3，因此 total 得到 36。第三行只改变 quantity，没有再次计算 total。

| 执行后 | quantity | total |
| --- | --- | --- |
| 第 1 行 | 3 | 尚未赋值 |
| 第 2 行 | 3 | 36 |
| 第 3 行 | 4 | 36 |

跟踪代码时，先记录旧值，再执行当前语句。不要用后面的值“倒推修改”前面的结果。

## 条件决定走哪条路

**条件 Condition** 是可以判断真或假的表达式。Python 用 `if` 在条件成立时执行缩进的代码；条件不成立时，可以执行 `else` 分支。

```python
score = 60
if score >= 60:
    result = "pass"
else:
    result = "retry"
print(result)
```

`>=` 包含等于，所以结果是 `pass`。如果把条件改成 `score > 60`，当 score 恰好是 60 时结果会变成 `retry`。这种刚好等于临界值的情况叫**边界情况**。

Python 的缩进决定语句归属。上例最后一行没有缩进，无论走哪个分支，最后都会显示 result。

对照 C#，条件放在圆括号中，代码块使用花括号：

```csharp
int score = 60;
string result;
if (score >= 60) {
    result = "pass";
} else {
    result = "retry";
}
System.Console.WriteLine(result);
```

这里两种语言都是选中一个分支。**看到 if，先算条件；条件确定后，只跟踪实际执行的分支。**

## 循环：每一轮都更新状态

**循环 Loop** 用于重复执行一组步骤。Python 的 `range(1, 4)` 在下面循环中依次提供 1、2、3，**不包含结束值 4**。

```python
total = 0
for number in range(1, 4):
    total = total + number
print(total)
```

| 轮次 | number | 更新前 total | 更新后 total |
| --- | --- | --- | --- |
| 1 | 1 | 0 | 1 |
| 2 | 2 | 1 | 3 |
| 3 | 3 | 3 | 6 |

`total = total + number` 不表示数学上的等式。它表示先读取旧 total 与本轮 number 相加，再把新结果赋给 total。输出为 6。

对应的 C# 循环可以写成：

```csharp
int total = 0;
for (int number = 1; number < 4; number++) {
    total = total + number;
}
System.Console.WriteLine(total);
```

依次检查初始化、继续条件和每轮更新：从 1 开始，小于 4 时执行，每轮加 1。最后仍然只处理 1、2、3。

若把 `total = 0` 放进循环体，每一轮都会清零，就不能累积之前的结果。**先看初始状态，再看边界，最后逐轮跟踪**，是本课最重要的方法。

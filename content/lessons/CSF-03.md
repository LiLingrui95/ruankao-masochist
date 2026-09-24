## 一组数据：位置和数值分开看

先修自查：`range(0, 3)` 会提供哪些数？答案是 0、1、2。若不确定，先复习第 2 单元循环小节。

假设你记录了三天的学习分钟数：15、25、10。Python 可以用一个 list 保存它们：

```python
minutes = [15, 25, 10]
print(minutes[1])
```

**元素 Element** 是集合中的一个值；**索引 Index** 是访问元素的位置编号。这里从 0 开始编号，所以索引 1 对应第二个元素，输出 25。

| 非负索引 | 0 | 1 | 2 |
| --- | --- | --- | --- |
| 元素 | 15 | 25 | 10 |

列表的长度 `len(minutes)` 是 3。长度表示元素的数量，不是最后一个元素的非负索引；最后一个非负索引为 2。

本单元只讨论非负索引。Python 还支持负索引，但不能把这个规则直接套用到 C# 普通数组。

## 遍历与边界

**遍历 Traversal** 指按某种顺序访问集合中的元素。只需要元素值时，可以直接遍历：

```python
minutes = [15, 25, 10]
total = 0
for value in minutes:
    total = total + value
print(total)
```

total 依次从 0 变成 15、40、50，最后输出 50。这里 value 是元素本身，不是索引。

需要位置时，可以遍历索引：

```python
minutes = [15, 25, 10]
for index in range(len(minutes)):
    print(index, minutes[index])
```

输出三行，分别是 `0 15`、`1 25`、`2 10`。`range(3)` 提供 0、1、2，正好是这里的有效非负索引。

若访问 `minutes[3]`，就越过了末尾，Python 会产生 `IndexError`；不会自动得到 0 或最后一个元素。空列表长度为 0，使用 `range(len(empty))` 的循环执行 0 次，不能访问它的第一个元素。

## Python list 与 C# 数组

它们都能按位置访问元素，但不是完全相同的数据结构。

```python
minutes = [15, 25, 10]
minutes.append(20)
print(len(minutes))
```

Python list 可以追加元素，此时长度变为 4。你暂时只需认识 `append()` 是向末尾追加一个元素，不必现在学习它的内部实现。

C# 的普通数组创建后长度固定，但已有元素的值可以改变：

```csharp
int[] minutes = {15, 25, 10};
minutes[1] = 30;
System.Console.WriteLine(minutes.Length);
System.Console.WriteLine(minutes[1]);
```

依次显示 3 和 30。**长度固定不等于元素不能修改。** C# 还有可变长的 `List<T>`，本课不把它与普通数组混用。

再看 Python 的修改：`minutes[1] = 30` 改的是第二个元素，`index = 1` 只是给一个变量赋值；修改索引变量本身不会自动改变集合。

完成本课后，检查自己能否回答：位置是几？这个位置存了什么？循环是否会越界？这三个问题将直接帮助你阅读后续查找与排序代码。

"""Demonstrate common list operations with short, easy-to-understand printed explanations.

Each operation is printed right before it's performed so the output shows both the
explanation (what the operation does) and the resulting list state.
"""

# Starting list
list1 = [1, 4, 7, 5, 3, 4, 5]
print("Initial list:", list1)

print("Replace element at index 2 with 10 (changes the 3rd element).")
list1[2] = 10
print("After replacing index 2:", list1)

print("Append 20 to the end of the list.")
list1.append(20)
print("After append:", list1)

print("Remove the first occurrence of the value 4.")
list1.remove(4)
print("After remove(4):", list1)



print("Print the length of the list.")
print("Length:", len(list1))

print("Remove and return the element at index 4 using pop().")
popped = list1.pop(4)
print("Popped element:", popped)
print("After pop:", list1)

print("Insert 15 at index 2 (shifts elements to the right).")
list1.insert(2, 15)
print("After insert:", list1)

print("Count how many times 5 appears in the list.")
print("Count of 5:", list1.count(5))

print("Sort the list in ascending order.")
list1.sort()
print("After sort:", list1)

print("Reverse the list in-place (flip order).")
list1.reverse()
print("After reverse:", list1)



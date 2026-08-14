
k = int(input("enter til :"))


for num in range(2, k):
    for i in range(2, num):
        if num % i == 0:
            break
    else:
        print(num,end=" ")
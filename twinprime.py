def prime(n):
    count = 0

    for i in range(1, n + 1):
        if n % i == 0:
            count = count + 1

    return count == 2


for n in range(3, 1000, 2):
    if prime(n) and prime(n + 2):
        print(n, n + 2)
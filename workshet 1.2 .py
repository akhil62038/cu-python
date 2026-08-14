n = int(input("Enter n: "))
r = int(input("Enter r: "))

fact_n = 1
for i in range(1, n + 1):
    fact_n = fact_n * i

fact_r = 1
for i in range(1, r + 1):
    fact_r = fact_r * i

fact_nr = 1
for i in range(1, n - r + 1):
    fact_nr = fact_nr * i

p = fact_n // fact_nr
c = fact_n // (fact_r * fact_nr)

print("Permutation:", p)
print("Combination:", c)
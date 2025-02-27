def is_imo_valid(imo):
    if imo is None or len(imo) != 7:
        return False
    a = list(imo)
    sum_ = 0
    for i in range(6):
        sum_ += (int(a[i])) * (len(a) - i)
    return sum_ % 10 == int(a[6])

def main():
    a = 0  # 1
    b = 0
    c = 0  # 3
    d = 0
    e = 0  # 5
    f = 0
    g = 0  # 7
    imo = ""
    while imo.lower() != "9999999":
        imo = f"{a}{b}{c}{d}{e}{f}{g}"
        if is_imo_valid(imo):
            print(imo)
        g += 1
        if g == 9:
            g = 0
            f += 1
            if f == 9:
                f = 0
                e += 1
                if e == 9:
                    e = 0
                    d += 1
                    if d == 9:
                        d = 0
                        c += 1
                        if c == 9:
                            c = 0
                            b += 1
                            if b == 9:
                                b = 0
                                a += 1
                                if a == 9:
                                    break

if __name__ == "__main__":
    main()


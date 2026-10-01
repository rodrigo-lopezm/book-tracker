def clean_isbn(raw_isbn: str) -> str:
    raw_isbn = raw_isbn.strip()
    return raw_isbn.replace("-", "").replace(" ", "")

def _validate_isbn10(isbn: str) -> bool:
    if isbn[0:9].isdigit():
        checksum10 = 0
        for i in range(9):
            checksum10 += int(isbn[i]) * (10 - i)
        if isbn[9].upper() == "X":
            checksum10 += 10
        elif isbn[9].isdigit():
            checksum10 += int(isbn[9])
        else:
            return False

        if checksum10 % 11 == 0:
            return True
    return False

def _validate_isbn13(isbn: str) -> bool:
    checksum13 = 0
    if isbn.isdigit():
        for i in range(13):
            if i % 2 == 0:
                checksum13 += int(isbn[i]) * 1
            else:
                checksum13 += int(isbn[i]) * 3
        if checksum13 % 10 == 0:
            return True
    return False

def validate_isbn(isbn: str) -> bool:
    isbn = clean_isbn(isbn)
    if len(isbn) == 10:
        return _validate_isbn10(isbn)
    elif len(isbn) == 13:
        return _validate_isbn13(isbn)
    return False
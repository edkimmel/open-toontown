BANK_MOVIE_CLEAR = 1
BANK_MOVIE_GUI = 2
BANK_MOVIE_DEPOSIT = 3
BANK_MOVIE_WITHDRAW = 4
BANK_MOVIE_NO_OP = 5
BANK_MOVIE_NOT_OWNER = 6
BANK_MOVIE_NO_OWNER = 7


def clampTransfer(av, amount):
    # the same four limits BankGUI.__updateTransaction applies
    # client-side (BankGUI.py:74-77), re-applied so a forged amount
    # cannot move more than the jar/bank allow; shared by every AI-side
    # sender of transferMoney so a clamp fix lands in one place
    jarMoney = av.getMoney()
    maxJarMoney = av.getMaxMoney()
    bankMoney = av.getBankMoney()
    maxBankMoney = av.getMaxBankMoney()
    amount = min(amount, jarMoney)
    amount = min(amount, maxBankMoney - bankMoney)
    amount = -min(-amount, maxJarMoney - jarMoney)
    amount = -min(-amount, bankMoney)
    return amount

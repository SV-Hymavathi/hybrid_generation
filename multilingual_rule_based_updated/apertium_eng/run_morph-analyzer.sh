# lt-proc -g -c hi.gen_LC.bin $1 > $1-out.txt

# echo "Your test sentence here" | apertium -d . eng-morph


apertium-destxt $1 | lt-proc -ac eng.automorf.bin | apertium-retxt > $1-out.txt
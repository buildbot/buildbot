#!/bin/bash

FILES=()
EXIT_CODE=0
while read filename; do
  extension="${filename##*.}"
  if [[ $extension == "py" && -f $filename ]]; then
        if [[ "$filename" =~ "/contrib/" || "$filename" =~ "master/docs" || "$filename" =~ "setup.py" ]]; then
          echo "not processing file: $filename"
        else
          echo "Will process file: $filename"
          FILES+=($filename)
       fi
  fi
done

echo "======== Checking Import module convention in modified files ========"

RES=true
for filename in ${py_files[@]}; do
  python common/fiximports.py "$filename"
  if [[ $? != 0 ]]; then
    echo "cannot fix imports of $filename"
    RES=false
  fi
done

if [[ $RES == false ]]; then
  echo "======= Some import fix could be done. not enforcing for now  ========"
else
  echo "========================== No error found ==========================="
fi

if [[ -z `which autopep8` ]]; then
    echo "please 'pip install autopep8' in order to automatically fix your pep8 issues"
else
    echo "============================== Auto pep8 =============================="

    for filename in ${py_files[@]}; do
      if [[ -f common/pep8rc ]]; then
        LINEWIDTH=$(grep -E "max-line-length" common/pep8rc | sed 's/ //g' | cut -d'=' -f 2)
        # even if we dont enforce errors, if they can be fixed automatically, thats better..
        IGNORES=E501,W6
        # ignore is not None for sqlaclhemy code..
        if [[ "$filename" =~ "/db/" ]]; then
          IGNORES=$IGNORES,E711,E712
        fi
        autopep8 --in-place --max-line-length=$LINEWIDTH --ignore=$IGNORES "$filename"
      else
        echo "No pep8rc found. Discard"
      fi
    done
    echo "=========================== autopep8 done ============================="
fi
if [[ -z `which pep8` ]]; then
    echo "please 'pip install pep8' in order to automatically check your pep8 issues"
else
    echo "=============================== Pep8 =================================="

    if [[ -f common/pep8rc ]]; then
      for filename in ${py_files[@]}; do
        pep8 --config=common/pep8rc "$filename"
        if [[ $? != 0 ]]; then
          echo "pep8 issues"
          EXIT_CODE=1
        fi
      done
    else
      echo "No pep8rc found. Discard"
    fi
    echo "============================= Pep8 done ==============================="
fi
if [[ -z `which pylint` ]]; then
    echo "please 'pip install pylint' in order to automatically fix your pylint issues"
else
    echo "==========================  Pylint =========================="

    if [[ -f common/pylintrc ]]; then
      for filename in ${py_files[@]}; do
            pylint --rcfile=common/pylintrc --disable=R,line-too-long --enable=W0611 --output-format=text --report=no "$filename"
            if [[ $? != 0 ]]; then
              echo "pylint issues"
              EXIT_CODE=1
            fi
      done
    else
      echo "No pylintrc found. Discard"
    fi
fi
exit $EXIT_CODE

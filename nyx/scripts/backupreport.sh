echo "************************"
echo "* Creating Report File *"
echo "************************"

cd /home/nyxinstall/nyx/backup/

echo "- Deleting Zip"
rm ./backupreport.zip

echo "- Deleting Tmp folder"
rm -d -r ./tempzipreport

echo "- Creating Tmp folder"
mkdir ./tempzipreport

echo "find /home/nyx/reportrunner/notebooks -type f -name '*.*' | grep -v -E '\/.ipynb' | grep -E '\\.ipynb|\\.docx'"
files="$(find /home/nyxinstall/nyx/reportrunner/notebooks -type f -name '*.*' | grep -v -E '\/.ipynb' | grep -E '\.ipynb|\.docx')"


echo "-----> $files"

#lines=( $files )

echo "======"
echo ${lines}
echo "======"

IFS=$'\n'

for line in ${files}
do
        echo "LINE=--> $line"
        template=$(echo $line | sed 's/^\.\./\.\/tempzipreport/g')
        template2=$(echo $template | sed -e 's!\(.*\)/\([^/]*\)$!\1!g')

        template2='/home/nyxinstall/nyx/backup/tempzipreport'

        echo "==> $template ==> $template2"
        mkdir -p $template2
        cp "$line" "$template2"
done

oldzip="./reports/backupreport.zip.prev"
newzip="./reports/backupreport.zip"

echo "- Creating Zip"
zip --password aimeleslapins -r $newzip ./tempzipreport/


if test -f "$oldzip"; then
    echo "$oldzip exist."

    prevsize=$(du -b $oldzip | cut -f1)
    cursize=$(du -b $newzip | cut -f1)

    echo "du -b $oldzip | cut -f1"
    echo "SIZE $prevsize <> $cursize"

#    similar=$(cmp $oldzip $newzip)
#    echo "$(cmp $oldzip $newzip)"
#    echo ">>>$similar<<<"
    if [ "$prevsize" == "$cursize" ]; then
      echo "Nothing changed"
    else
      echo "File changed"
      cp $newzip $oldzip
      cp $newzip ./reports/reports.zip
    fi
   
else
    echo "$oldzip does not exist."
    cp $newzip $oldzip
    cp $newzip ./reports/reports.zip
fi

echo "- Finished"


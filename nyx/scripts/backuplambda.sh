echo "************************"
echo "* Creating Lambda File *"
echo "************************"

cd /home/nyxinstall/nyx/backup/

echo "- Deleting Zip"
rm ./backuplambda.zip

echo "- Deleting Tmp folder"
rm -d -r ./tempziplambda

echo "- Creating Tmp folder"
mkdir ./tempziplambda


#mkdir ./tempzip/reportrunner
#cp -d -R /home/nyx/reportrunner/notebooks ./tempzip/reportrunner

files="$(find /home/nyxinstall/nyx/notebooks/Lambdas -type f -name '*.ipynb'| grep -v -E '\/.ipynb')"

echo "-----> $files"

#lines=( $files )

echo "======"
echo ${lines}
echo "======"

IFS=$'\n'

for line in ${files}
do
        echo "LINE=--> $line"
        template=$(echo $line | sed 's/^\.\./\.\/tempziplambda/g')
        template2=$(echo $template | sed -e 's!\(.*\)/\([^/]*\)$!\1!g')

        template2='/home/nyxinstall/nyx/backup/tempziplambda'

        echo "==> $template ==> $template2"
        mkdir -p $template2
        cp "$line" "$template2"
done

oldzip="./lambdas/backuplambda.zip.prev"
newzip="./lambdas/backuplambda.zip"

echo "- Creating Zip"
pwd
echo  "$newzip"
zip --password aimeleslapins -r $newzip ./tempziplambda/


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
      cp $newzip ./lambdas/lambdas.zip
    fi
   
else
    echo "$oldzip does not exist."
    cp $newzip $oldzip
    cp $newzip ./lambdas/lambdas.zip
fi

echo "- Finished"

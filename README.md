# Tree2Bash - Tree Structure to Bash Script Generator

## tree2bash
translate project structure in tree text format to bash script

## when to use
when you copy a project structure from deepseek generated text
store it in a text file
the python program read a UTF-8 Unicode text file that store the project structure you copy from deepseek
output a bash script file
you run the bash script file to create the directory structure on your computer.

## develop story
I want see a big project structure that deepseek generated, in the beginning I copy it in file
change it to bash script by hand, but the work is easy but long time, I can't accept.
I try write this program first , but fail
unitl today I find the right way to work with deepseek
I follow the compiler stage
first step : let deepseek implement a lexical analyzer
let deepseek change it to my wanted
second step : I write a grammar base on the project structure
let deepseek give me ebnf version
third step : let deepseek base on the grammar and lexical analyzer, wirte a syntax analyzer
forth step : let deepseek write a function that can reconstruct the original file
             reconstruct(parse(tokenize(input file))) = input file
fifth step : I change this reconstruct function to a generator function
             add my need logic into the function
             do some print and try
             finally I get I want!
the program is not perfect. but work on my computer

## Grammar

```
FileEntry     = { LineElement }
LineElement   = Prefix, (DirectoryName | Filename), Postfix
Prefix        = { PrefixChar }
PrefixChar    = UnicodeChar | Whitespace
Postfix       = { MiddleChar }, Terminator
MiddleChar    = Whitespace
Terminator    = Newline | Comment

Terminal symbols:
- DirectoryName: name ending with /
- Filename: any valid filename
- Whitespace: spaces, tabs
- Newline: \n, \r, \f, \v
- Comment: text after #
- UnicodeChar: any Unicode character
```

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- DeepSeek
- Python

## Version History

See [CHANGELOG.md](CHANGELOG.md) for details.

## Author

He Wei Wei

## Support

- 📧 Email: yijiu86@qq.com
- WeChat: whoweiwei

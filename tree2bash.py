#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tree Structure Parser for UTF-8 Unicode Text Files
Parses tree-like directory structure output and generates bash script.

Grammar:
    FileEntry = { LineElement };
    LineElement = Prefix, (DirectoryName | Filename), Postfix;
    Prefix = { PrefixChar };
    PrefixChar = UnicodeChar | Whitespace;
    Postfix = { MiddleChar }, Terminator;
    MiddleChar = Whitespace
    Terminator = Newline | Comment;
    
Terminal symbols:
    DirectoryName = DIRECTORY_NAME TOKEN (ends with / or \)
    Filename = FILENAME TOKEN (any valid filename, no dot required)
    Whitespace = WHITESPACE TOKEN
    Newline = NEWLINE TOKEN
    Comment = COMMENT TOKEN
    UnicodeChar = UNICODE_CHAR TOKEN
"""

import sys
import os
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any, Set
from dataclasses import dataclass, field
import unicodedata
import ast

# ============================================================================
# LEXICAL ANALYZER
# ============================================================================

class TokenType(Enum):
    """Enumeration of all token types"""
    DIRECTORY_NAME = "DIRECTORY_NAME"  # New: identifier ending with / or \
    COMMENT = "COMMENT"
    FILENAME = "FILENAME"  # Modified: no dot required
    WHITESPACE = "WHITESPACE"
    NEWLINE = "NEWLINE"
    UNICODE_CHAR = "UNICODE_CHAR"
    UNKNOWN = "UNKNOWN"
    EOF = "EOF"

@dataclass
class Token:
    """Token class representing a lexical unit"""
    type: TokenType
    value: str
    line: int
    column: int
    file_info: Optional[str] = None
    
    def __repr__(self):
        return f"Token({self.type}, '{self.value}', line={self.line}, col={self.column})"
    
    def __str__(self):
        file_info_str = f" [{self.file_info}]" if self.file_info else ""
        return f"{self.type.value:14} | {self.value:25} | line {self.line:4}, col {self.column:4}{file_info_str}"

class LexicalAnalyzer:
    """Lexical analyzer for tree-like UTF-8 directory structure text"""
    
    # Unicode tree-drawing characters
    TREE_CHARS = {
        '│', '├', '└', '─', '┬', '┌', '┐', '┘', '└', '├', '┤', '┴', '┬', '┼',
        '╵', '╷', '╶', '╴', '╎', '╏', '╿', '╽', '╼', '╾',
    }
    
    def __init__(self, text: str, filename: str = "<input>"):
        self.text = text
        self.filename = filename
        self.position = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
        self.line_start = True
    
    def is_whitespace(self, char: str) -> bool:
        return char and (char == ' ' or char == '\t' or 
                        unicodedata.category(char).startswith('Z'))
    
    def is_horizontal_whitespace(self, char: str) -> bool:
        return char and (char == ' ' or char == '\t' or 
                        char in '\u00A0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A\u202F\u205F\u3000')
    
    def is_newline(self, char: str) -> bool:
        return char in '\n\r\f\v'
    
    def is_digit(self, char: str) -> bool:
        return char and unicodedata.category(char) == 'Nd'
    
    def is_letter(self, char: str) -> bool:
        if not char:
            return False
        cat = unicodedata.category(char)
        return cat.startswith('L')
    
    def is_tree_char(self, char: str) -> bool:
        """Check if character is a tree-drawing Unicode character"""
        return char in self.TREE_CHARS
    
    def is_filename_char(self, char: str) -> bool:
        """Valid characters for filenames and directory names"""
        if not char:
            return False
        # Allow letters, digits, common filename chars
        # Exclude path separators and tree chars to avoid confusion
        if char in '/\\':
            return False
        if self.is_tree_char(char):
            return False
        if self.is_newline(char):
            return False
        return (self.is_letter(char) or 
                self.is_digit(char) or 
                char in '_-~ .+()[]{}@#$%^&=!' or
                unicodedata.category(char) == 'Mn')
    
    def is_name_char(self, char: str) -> bool:
        if not char:
            return False
        if self.is_horizontal_whitespace(char):
            return False
        if self.is_tree_char(char):
            return False
        if self.is_newline(char):
            return False
        return (self.is_letter(char) or 
                self.is_digit(char) or 
                char == '_' or char == '.' or char == '/' or unicodedata.category(char) == 'Mn')

    def is_identifier_part(self, char: str) -> bool:
        if not char:
            return False
        return (self.is_letter(char) or 
                self.is_digit(char) or 
                char == '_' or
                unicodedata.category(char) == 'Mn')
    
    def is_unix_file_name_start(self, char: str) -> bool:
        if not char:
            return False
        if char == '/':
            return False
        if char == '\0':
            return False
        return True
    def is_mac_file_name_start(self, char: str) -> bool:
        if not char:
            return False
        if char == '/':
            return False
        if char == ':':
            return False
        return True
    def is_windows_file_name_start(self, char: str) -> bool:
        if not char:
            return False
        if char in '/\\:*?"<>|':
            return False
        return True

    def is_identifier_start(self, char: str) -> bool:
        if not char:
            return False
        return self.is_letter(char) or char == '_'
    def is_allowed_name_start(self, char: str) -> bool:
        if not char:
            return False
        return self.is_letter(char) or char == '_' or char == '.'
   
    def get_next_char(self) -> Optional[str]:
        if self.position >= len(self.text):
            return None
        return self.text[self.position]
    
    def advance(self) -> Optional[str]:
        if self.position >= len(self.text):
            return None
        char = self.text[self.position]
        self.position += 1
        if char == '\n':
            self.line += 1
            self.column = 1
            self.line_start = True
        else:
            self.column += 1
        return char
    
    def peek_next_char(self) -> Optional[str]:
        if self.position + 1 >= len(self.text):
            return None
        return self.text[self.position + 1]
    
    def read_whitespace(self) -> Tuple[str, int, int]:
        start_line = self.line
        start_col = self.column
        value = ''
        while True:
            char = self.get_next_char()
            if char and self.is_horizontal_whitespace(char):
                value += self.advance()
            else:
                break
        return value, start_line, start_col
    
    
    def read_name(self) -> Tuple[Optional[str], int, int, bool]:
        """
        Read a filename or directory name.
        Returns (value, start_line, start_col, is_directory)
        is_directory is True if name ends with / or \
        """
        start_line = self.line
        start_col = self.column
        value = ''
        
        # Read all valid filename characters
        while True:
            char = self.get_next_char()
            #if char and self.is_filename_char(char):
            if char and self.is_name_char(char):
                value += self.advance()
            else:
                break
        
        if not value:
            return None, start_line, start_col, False
        
        # Check if it ends with path separator (directory)
        is_directory = False
        if value and value[-1] in '/\\':
            is_directory = True
            value = value.rstrip('/\\')  # Store without the separator
        # my fix
        # my add function to deterimaine is directory
        if not is_directory:
            char = self.get_next_char()
            if char and char in '/\\':
                is_directory = True
        return value, start_line, start_col, is_directory
    
    def read_comment(self, comment_type: str = '#') -> Tuple[str, int, int]:
        start_line = self.line
        start_col = self.column
        value = ''
        if comment_type == '#':
            self.advance()
        while True:
            char = self.advance()
            if char is None or self.is_newline(char):
                break
            value += char
        return value, start_line, start_col
    
    def tokenize(self) -> List[Token]:
        self.tokens = []
        while self.position < len(self.text):
            char = self.get_next_char()
            
            # Handle newlines
            if char and self.is_newline(char):
                newline_char = self.advance()
                self.tokens.append(Token(TokenType.NEWLINE, newline_char, self.line - 1, self.column - 1))
                self.line_start = True
                continue
            
            # Handle horizontal whitespace (spaces, tabs)
            if char and self.is_horizontal_whitespace(char):
                value, line, col = self.read_whitespace()
                self.tokens.append(Token(TokenType.WHITESPACE, value, line, col))
                self.line_start = False
                continue
            
            self.line_start = False
            
            # Handle comments
            if char == '#':
                value, line, col = self.read_comment('#')
                self.tokens.append(Token(TokenType.COMMENT, value, line, col))
                continue
            
            if char and self.is_allowed_name_start(char):
                #or self.is_digit(char) or char in '.-_~'):
                name_result = self.read_name()
                if name_result[0] is not None:
                    value, line, col, is_directory = name_result
                    if is_directory:
                        self.tokens.append(Token(TokenType.DIRECTORY_NAME, value, line, col))
                    else:
                        self.tokens.append(Token(TokenType.FILENAME, value, line, col))
                    continue
           
            # Handle tree-drawing characters
            if char and self.is_tree_char(char):
                value = self.advance()
                # Treat tree chars as Unicode characters
                self.tokens.append(Token(TokenType.UNICODE_CHAR, value, self.line, self.column - 1))
                continue
            
            # Handle any other Unicode characters
            value = self.advance()
            if value and unicodedata.category(value) not in ('Cc', 'Cf'):
                self.tokens.append(Token(TokenType.UNICODE_CHAR, value, self.line, self.column - 1))
            else:
                self.tokens.append(Token(TokenType.UNKNOWN, value, self.line, self.column - 1))
            # need put filename find in last
            # need remove all don't need token
        
        self.tokens.append(Token(TokenType.EOF, 'EOF', self.line, self.column))
        return self.tokens

# ============================================================================
# SYNTAX ANALYZER
# ============================================================================

class ParseNodeType(Enum):
    """Types of parse tree nodes"""
    FILE_ENTRY = "FileEntry"
    LINE_ELEMENT = "LineElement"
    PREFIX = "Prefix"
    PREFIX_CHAR = "PrefixChar"
    POSTFIX = "Postfix"
    MIDDLE_CHAR = "MiddleChar"
    TERMINATOR = "Terminator"
    DIRECTORY_NAME = "DirectoryName"  # New
    FILENAME = "Filename"
    WHITESPACE = "Whitespace"
    NEWLINE = "Newline"
    COMMENT = "Comment"
    UNICODE_CHAR = "UnicodeChar"
    TOKEN = "Token"
    EOF = "EOF"

@dataclass
class ParseNode:
    """Node in the parse tree"""
    type: ParseNodeType
    value: str = ""
    children: List['ParseNode'] = field(default_factory=list)
    token: Optional[Token] = None
    line: int = 0
    column: int = 0
    
    def add_child(self, child: 'ParseNode') -> 'ParseNode':
        self.children.append(child)
        return self
    
    def add_children(self, children: List['ParseNode']) -> 'ParseNode':
        self.children.extend(children)
        return self
    
    def __repr__(self, level=0, max_depth=10):
        if level > max_depth:
            return f"{'  ' * level}...\n"
        
        indent = "  " * level
        result = f"{indent}{self.type.value}"
        if self.value:
            result += f" '{self.value}'"
        if self.token:
            result += f" [line {self.token.line}, col {self.token.column}]"
        if not self.children:
            result += " (terminal)"
        result += "\n"
        
        for child in self.children[:20]:
            result += child.__repr__(level + 1, max_depth)
        if len(self.children) > 20:
            result += f"{'  ' * (level + 1)}... and {len(self.children) - 20} more children\n"
        
        return result

class SyntaxAnalyzer:
    """
    Syntax analyzer implementing the grammar:
        FileEntry = { LineElement };
        LineElement = Prefix, (DirectoryName | Filename), Postfix;
        Prefix = { PrefixChar };
        PrefixChar = UnicodeChar | Whitespace;
        Postfix = { MiddleChar }, Terminator;
        MiddleChar = Whitespace
        Terminator = Newline | Comment;
    
    Terminal symbols:
        DirectoryName = DIRECTORY_NAME TOKEN
        Filename = FILENAME TOKEN
        Whitespace = WHITESPACE TOKEN
        Newline = NEWLINE TOKEN
        Comment = COMMENT TOKEN
        UnicodeChar = UNICODE_CHAR TOKEN
    """
    
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.position = 0
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.parse_tree = None
        self.line_elements: List[ParseNode] = []
    
    def current_token(self) -> Optional[Token]:
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None
    
    def peek_token(self, offset: int = 1) -> Optional[Token]:
        pos = self.position + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return None
    
    def advance(self) -> Optional[Token]:
        if self.position < len(self.tokens):
            token = self.tokens[self.position]
            self.position += 1
            return token
        return None
    
    def match(self, *expected_types: TokenType) -> Optional[Token]:
        token = self.current_token()
        if token and token.type in expected_types:
            return self.advance()
        return None
    
    def expect(self, *expected_types: TokenType) -> Optional[Token]:
        token = self.current_token()
        if token and token.type in expected_types:
            return self.advance()
        
        if token:
            expected_names = [t.value for t in expected_types]
            actual_name = token.type.value
            self.errors.append(f"Expected {', '.join(expected_names)}, got {actual_name} at line {token.line}, col {token.column}")
        else:
            self.errors.append(f"Expected {', '.join(expected_names)}, got EOF")
        return None
    
    def parse(self) -> ParseNode:
        """
        FileEntry = { LineElement };
        Parse multiple line elements until EOF
        """
        self.position = 0
        self.errors = []
        self.warnings = []
        self.line_elements = []
        
        file_node = ParseNode(ParseNodeType.FILE_ENTRY)
        
        while True:
            token = self.current_token()
            if not token or token.type == TokenType.EOF:
                break
            
            # Parse a single line element
            line_node = self.parse_line_element()
            if line_node:
                file_node.add_child(line_node)
                self.line_elements.append(line_node)
            else:
                if token:
                    self.errors.append(f"Unable to parse line element at line {token.line}, col {token.column}")
                    self.advance()
                else:
                    break
        
        self.parse_tree = file_node
        return file_node
    
    def parse_line_element(self) -> Optional[ParseNode]:
        """
        LineElement = Prefix, (DirectoryName | Filename), Postfix;
        """
        start_token = self.current_token()
        if not start_token:
            return None
        
        line_node = ParseNode(ParseNodeType.LINE_ELEMENT)
        line_node.line = start_token.line
        line_node.column = start_token.column
        
        # Parse Prefix
        prefix_node = self.parse_prefix()
        line_node.add_child(prefix_node)
        
        # Parse main content: DirectoryName or Filename
        main_node = self.parse_main_content()
        if main_node:
            line_node.add_child(main_node)
        else:
            token = self.current_token()
            if token:
                self.errors.append(f"Expected DirectoryName or Filename at line {token.line}, col {token.column}, got {token.type.value}")
            else:
                self.errors.append("Expected DirectoryName or Filename, got EOF")
            return None
        
        # Parse Postfix
        postfix_node = self.parse_postfix()
        line_node.add_child(postfix_node)
        
        return line_node
    
    def parse_prefix(self) -> ParseNode:
        """
        Prefix = { PrefixChar };
        PrefixChar = UnicodeChar | Whitespace;
        """
        prefix_node = ParseNode(ParseNodeType.PREFIX)
        
        while True:
            token = self.current_token()
            if not token:
                break
            
            # Check if we've reached the main content
            if token.type in (TokenType.DIRECTORY_NAME, TokenType.FILENAME):
                break
            
            # Parse prefix character
            prefix_char_node = self.parse_prefix_char()
            if prefix_char_node:
                prefix_node.add_child(prefix_char_node)
            else:
                break
        
        return prefix_node
    
    def parse_prefix_char(self) -> Optional[ParseNode]:
        """
        PrefixChar = UnicodeChar | Whitespace;
        """
        token = self.current_token()
        if not token:
            return None
        
        node = ParseNode(ParseNodeType.PREFIX_CHAR)
        
        if token.type == TokenType.WHITESPACE:
            token = self.advance()
            child = ParseNode(ParseNodeType.WHITESPACE, repr(token.value), token=token)
            node.add_child(child)
            return node
        
        elif token.type == TokenType.UNICODE_CHAR:
            token = self.advance()
            child = ParseNode(ParseNodeType.UNICODE_CHAR, token.value, token=token)
            node.add_child(child)
            return node
        
        elif token.type == TokenType.UNKNOWN:
            token = self.advance()
            child = ParseNode(ParseNodeType.UNICODE_CHAR, token.value, token=token)
            node.add_child(child)
            self.warnings.append(f"Unknown token treated as UnicodeChar at line {token.line}, col {token.column}")
            return node
        
        return None
    
    def parse_main_content(self) -> Optional[ParseNode]:
        """
        DirectoryName | Filename
        """
        token = self.current_token()
        if not token:
            return None
        
        if token.type == TokenType.DIRECTORY_NAME:
            token = self.advance()
            node = ParseNode(ParseNodeType.DIRECTORY_NAME, token.value, token=token)
            node.line = token.line
            node.column = token.column
            return node
        
        elif token.type == TokenType.FILENAME:
            token = self.advance()
            node = ParseNode(ParseNodeType.FILENAME, token.value, token=token)
            node.line = token.line
            node.column = token.column
            return node
        
        return None
    
    def parse_postfix(self) -> ParseNode:
        """
        Postfix = { MiddleChar }, Terminator;
        MiddleChar = Whitespace
        Terminator = Newline | Comment;
        """
        postfix_node = ParseNode(ParseNodeType.POSTFIX)
        
        # Parse zero or more MiddleChar
        while True:
            token = self.current_token()
            if not token:
                break
            
            # Check if we've reached the terminator
            if token.type in (TokenType.NEWLINE, TokenType.COMMENT, TokenType.EOF):
                break
            
            # Parse MiddleChar
            middle_node = self.parse_middle_char()
            if middle_node:
                postfix_node.add_child(middle_node)
            else:
                break
        
        # Parse Terminator (required)
        terminator_node = self.parse_terminator()
        if terminator_node:
            postfix_node.add_child(terminator_node)
        else:
            token = self.current_token()
            if token:
                self.warnings.append(f"Expected Terminator (Newline or Comment) at line {token.line}, col {token.column}")
                eof_node = ParseNode(ParseNodeType.TERMINATOR)
                eof_child = ParseNode(ParseNodeType.NEWLINE, "EOF", token=token)
                eof_node.add_child(eof_child)
                postfix_node.add_child(eof_node)
            else:
                self.warnings.append("Reached EOF without Terminator")
        
        return postfix_node
    
    def parse_middle_char(self) -> Optional[ParseNode]:
        """
        MiddleChar = Whitespace
        """
        token = self.current_token()
        if not token:
            return None
        
        node = ParseNode(ParseNodeType.MIDDLE_CHAR)
        
        if token.type == TokenType.WHITESPACE:
            token = self.advance()
            child = ParseNode(ParseNodeType.WHITESPACE, repr(token.value), token=token)
            node.add_child(child)
            return node
        
        return None
    
    def parse_terminator(self) -> Optional[ParseNode]:
        """
        Terminator = Newline | Comment;
        """
        token = self.current_token()
        if not token:
            return None
        
        node = ParseNode(ParseNodeType.TERMINATOR)
        
        if token.type == TokenType.NEWLINE:
            token = self.advance()
            child = ParseNode(ParseNodeType.NEWLINE, repr(token.value), token=token)
            node.add_child(child)
            return node
        
        elif token.type == TokenType.COMMENT:
            token = self.advance()
            child = ParseNode(ParseNodeType.COMMENT, token.value, token=token)
            node.add_child(child)
            return node
        
        elif token.type == TokenType.EOF:
            token = self.advance()
            child = ParseNode(ParseNodeType.NEWLINE, "EOF", token=token)
            node.add_child(child)
            self.warnings.append("EOF treated as Terminator")
            return node
        
        return None
    
    def get_parse_tree(self) -> ParseNode:
        return self.parse_tree
    
    def print_parse_tree(self, max_depth: int = 8) -> None:
        if self.parse_tree:
            print("\n=== Parse Tree ===")
            print(self.parse_tree.__repr__(0, max_depth))
        else:
            print("No parse tree available")
    
    def print_errors(self) -> None:
        if self.errors:
            print("\n=== Parse Errors ===")
            for error in self.errors:
                print(f"  ✗ {error}")
        else:
            print("\n✓ No parsing errors")
    
    def print_warnings(self) -> None:
        if self.warnings:
            print("\n=== Parse Warnings ===")
            for warning in self.warnings:
                print(f"  ⚠ {warning}")
        else:
            print("\n✓ No parsing warnings")
    
    def validate(self) -> bool:
        return len(self.errors) == 0
    
    def print_summary(self) -> None:
        print("\n" + "="*80)
        print("PARSE SUMMARY")
        print("="*80)
        
        print(f"\nTotal tokens: {len(self.tokens)}")
        print(f"Line elements: {len(self.line_elements)}")
        print(f"Parse errors: {len(self.errors)}")
        print(f"Parse warnings: {len(self.warnings)}")
        
        self.print_errors()
        self.print_warnings()
        
        if self.validate():
            print(f"\n✓ Valid parse - Grammar rule: FileEntry = {{ LineElement }}")
            print(f"  Each LineElement = Prefix, (DirectoryName | Filename), Postfix")
        else:
            print(f"\n✗ Invalid parse")
        
        if self.line_elements:
            dir_count = sum(1 for el in self.line_elements if el.children and len(el.children) > 1 and el.children[1].type == ParseNodeType.DIRECTORY_NAME)
            file_count = sum(1 for el in self.line_elements if el.children and len(el.children) > 1 and el.children[1].type == ParseNodeType.FILENAME)
            print(f"\nLine element breakdown:")
            print(f"  Directories: {dir_count}")
            print(f"  Files: {file_count}")
        
        token_counts = {}
        for token in self.tokens:
            token_counts[token.type] = token_counts.get(token.type, 0) + 1
        
        print("\n=== Token Statistics ===")
        for token_type, count in sorted(token_counts.items(), key=lambda x: x[1], reverse=True):
            if token_type != TokenType.EOF:
                print(f"  {token_type.value:14}: {count}")
    
    def print_line_elements(self) -> None:
        if not self.line_elements:
            print("\nNo line elements found")
            return
        
        print("\n" + "="*80)
        print("LINE ELEMENTS")
        print("="*80)
        
        for i, element in enumerate(self.line_elements, 1):
            print(f"\nLine {i}:")
            
            if not element.children:
                print("  (empty line element)")
                continue
            
            for child in element.children:
                if child.type == ParseNodeType.PREFIX:
                    prefix_chars = [c.children[0].type.value if c.children else "?" for c in child.children]
                    print(f"  Prefix: {len(child.children)} character(s)")
                    if child.children:
                        sample = ", ".join(prefix_chars[:5])
                        if len(child.children) > 5:
                            sample += f", ... and {len(child.children) - 5} more"
                        print(f"    [{sample}]")
                
                elif child.type in (ParseNodeType.DIRECTORY_NAME, ParseNodeType.FILENAME):
                    print(f"  Main: {child.type.value} '{child.value}'")
                
                elif child.type == ParseNodeType.POSTFIX:
                    middle_chars = [c.children[0].type.value if c.children else "?" for c in child.children if c.type == ParseNodeType.MIDDLE_CHAR]
                    terminators = [c.children[0].type.value if c.children else "?" for c in child.children if c.type == ParseNodeType.TERMINATOR]
                    
                    print(f"  Middle chars: {len(middle_chars)}")
                    if middle_chars:
                        print(f"    [{', '.join(middle_chars[:5])}]")
                    print(f"  Terminator: {', '.join(terminators) if terminators else 'None'}")


# ============================================================================
# BASH SCRIPT GENERATOR
# ============================================================================

def generate_bash_script(parse_tree: ParseNode, original_filename: str = None) -> Tuple[str, bool]:
    """
    Generate a bash script from the parse tree that creates the directory/file structure.
    Uses depth tracking based on prefix character count to determine cd .. commands.
    
    Args:
        parse_tree: The root parse node (FILE_ENTRY)
        original_filename: Optional path to original file for comparison
        
    Returns:
        Tuple of (bash_script_text, is_valid)
    """
    bash_lines = []
    bash_lines.append("#!/bin/bash")
    bash_lines.append("# Auto-generated bash script to create project structure")
    bash_lines.append("# Generated from parse tree analysis")
    bash_lines.append("")
    
    prev_prefix_char_count = 0
    depth_stack = []  # Stack to track directory depths
    
    def count_prefix_chars(prefix_node: ParseNode) -> int:
        """Count the number of characters in a prefix node"""
        return len(prefix_node.children)
    
    def escape_bash_string(value: str) -> str:
        """Escape a string for safe use in bash"""
        # Escape single quotes by ending quote, adding escaped quote, then restarting quote
        escaped = value.replace("'", "'\\''")
        return f"'{escaped}'"
    
    line_index = 0
    for element in parse_tree.children:
        if element.type != ParseNodeType.LINE_ELEMENT:
            continue
        
        if not element.children or len(element.children) < 2:
            continue
        
        prefix_node = element.children[0]

        main_node = element.children[1]
        
        if prefix_node.type != ParseNodeType.PREFIX:
            continue
        
        current_prefix_count = 0
        if prefix_node:
            i = 0
            while i<len(prefix_node.children):
                node = prefix_node.children[i]
                for child in node.children:
                    current_prefix_count += len(child.value)
                i+=1

        line_index += 1
        
        # Calculate depth change
        if current_prefix_count < prev_prefix_char_count:
            # Need to go up: (prev - current) / 4 directories
            depth_diff = (prev_prefix_char_count - current_prefix_count) // 4
            if depth_diff > 0:
                bash_lines.append(f"# Moving up {depth_diff} level(s)")
                for _ in range(depth_diff):
                    bash_lines.append("cd ..")
                    if depth_stack:
                        depth_stack.pop()
                bash_lines.append("")
        
        prev_prefix_char_count = current_prefix_count
        
        # Generate command based on type
        name = escape_bash_string(main_node.value)
        
        if main_node.type == ParseNodeType.DIRECTORY_NAME:
            bash_lines.append(f"# Creating directory: {main_node.value}")
            bash_lines.append(f"mkdir -p {name}")
            bash_lines.append(f"cd {name}")
            bash_lines.append("")
            depth_stack.append(main_node.value)
            
        elif main_node.type == ParseNodeType.FILENAME:
            bash_lines.append(f"# Creating file: {main_node.value}")
            bash_lines.append(f"touch {name}")
            bash_lines.append("")
    
    # Return to root directory at the end
    while depth_stack:
        bash_lines.append("cd ..")
        depth_stack.pop()
    
    bash_lines.append("")
    bash_lines.append("echo 'Project structure created successfully!'")
    
    bash_text = '\n'.join(bash_lines) + '\n'
    
    is_valid = len(bash_lines) > 4  # More than just header
    
    return bash_text, is_valid


def save_bash_script(script_text: str, output_path: str) -> None:
    """
    Save bash script to a file and make it executable.
    
    Args:
        script_text: The bash script content
        output_path: Path to save the script
    """
    try:
        with open(output_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(script_text)
        
        # Make executable on Unix-like systems
        try:
            os.chmod(output_path, 0o755)
            print(f"\n✅ Bash script saved and made executable: {output_path}")
        except:
            print(f"\n✅ Bash script saved: {output_path}")
            
        print(f"   Size: {len(script_text)} characters")
        print(f"   Lines: {script_text.count(chr(10))} lines")
        
        # Count commands
        mkdir_count = script_text.count("mkdir -p")
        touch_count = script_text.count("touch ")
        cd_up_count = script_text.count("cd ..")
        cd_down_count = script_text.count("cd ") - cd_up_count
        
        print(f"   Commands: {mkdir_count} mkdir, {touch_count} touch, {cd_down_count} cd (in), {cd_up_count} cd (out)")
        
    except Exception as e:
        print(f"\n❌ Error saving bash script: {e}")


def reconstruct_file(parse_tree: ParseNode, original_filename: str = None) -> Tuple[str, bool]:
    """
    Reconstruct the original UTF-8 text file from the parse tree.
    This is the original reconstruction function for verification purposes.
    
    Args:
        parse_tree: The root parse node (FILE_ENTRY)
        original_filename: Optional path to original file for comparison
        
    Returns:
        Tuple of (reconstructed_text, is_identical_to_original)
    """
    reconstructed_lines = []
    
    def extract_token_value(node: ParseNode) -> str:
        if node.token is not None:
            if node.type == ParseNodeType.WHITESPACE:
                try:
                    return ast.literal_eval(node.value) if node.value else ""
                except:
                    return node.token.value
            elif node.type == ParseNodeType.NEWLINE:
                try:
                    return ast.literal_eval(node.value) if node.value else ""
                except:
                    return node.token.value
            elif node.type == ParseNodeType.COMMENT:
                try:
                    return "#"+ast.literal_eval(node.value)+"\n" if node.value else ""
                except:
                    return "#"+node.token.value+"\n"
            else:
                return node.value if node.value else node.token.value
        
        result = ""
        for child in node.children:
            result += extract_token_value(child)
        return result
    
    def flatten_line_element(element: ParseNode) -> str:
        line_text = ""
        
        for child in element.children:
            if child.type == ParseNodeType.PREFIX:
                line_text += extract_token_value(child)
            
            elif child.type == ParseNodeType.DIRECTORY_NAME:
                if child.token:
                    line_text += child.token.value + "/"
                else:
                    line_text += child.value + "/"
            
            elif child.type == ParseNodeType.FILENAME:
                if child.token:
                    line_text += child.token.value
                else:
                    line_text += child.value
            
            elif child.type == ParseNodeType.POSTFIX:
                for postfix_child in child.children:
                    if postfix_child.type == ParseNodeType.MIDDLE_CHAR:
                        line_text += extract_token_value(postfix_child)
                    elif postfix_child.type == ParseNodeType.TERMINATOR:
                        line_text += extract_token_value(postfix_child)
        
        return line_text
    
    for element in parse_tree.children:
        if element.type == ParseNodeType.LINE_ELEMENT:
            line_text = flatten_line_element(element)
            reconstructed_lines.append(line_text)
    
    reconstructed_text = ''.join(reconstructed_lines)
    
    is_identical = False
    if original_filename:
        try:
            with open(original_filename, 'r', encoding='utf-8') as f:
                original_text = f.read()
            is_identical = (reconstructed_text == original_text)
            
            if is_identical:
                print("\n✅ PERFECT MATCH: Reconstructed file is identical to original!")
            else:
                print("\n❌ MISMATCH: Reconstructed file differs from original")
                print(f"  Original length: {len(original_text)} characters")
                print(f"  Reconstructed length: {len(reconstructed_text)} characters")
                
                for i, (c1, c2) in enumerate(zip(original_text, reconstructed_text)):
                    if c1 != c2:
                        start = max(0, i - 20)
                        end = min(len(original_text), i + 20)
                        print(f"\n  First difference at position {i}:")
                        print(f"  Original:      {repr(original_text[start:end])}")
                        print(f"  Reconstructed: {repr(reconstructed_text[start:end])}")
                        break
        except Exception as e:
            print(f"\n⚠️  Could not compare with original: {e}")
    
    return reconstructed_text, is_identical


def verify_parse_correctness(original_file: str, parse_tree: ParseNode, 
                            output_file: str = None) -> Dict[str, Any]:
    """
    Comprehensive verification of parse correctness.
    
    Args:
        original_file: Path to original UTF-8 file
        parse_tree: Parse tree from parser
        output_file: Optional path to save reconstructed file
        
    Returns:
        Dictionary with verification results
    """
    result = {
        'success': False,
        'identical': False,
        'original_length': 0,
        'reconstructed_length': 0,
        'differences': [],
        'reconstructed_text': '',
    }
    
    try:
        with open(original_file, 'r', encoding='utf-8') as f:
            original_text = f.read()
        result['original_length'] = len(original_text)
    except Exception as e:
        result['differences'].append(f"Cannot read original file: {e}")
        return result
    
    reconstructed_text, is_identical = reconstruct_file(parse_tree, original_file)
    result['reconstructed_text'] = reconstructed_text
    result['reconstructed_length'] = len(reconstructed_text)
    result['identical'] = is_identical
    
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(reconstructed_text)
            print(f"\n✅ Reconstructed file saved to: {output_file}")
        except Exception as e:
            print(f"\n❌ Error saving reconstructed file: {e}")
    
    if not is_identical:
        max_len = max(len(original_text), len(reconstructed_text))
        differences = []
        
        for i in range(max_len):
            if i >= len(original_text):
                differences.append(f"Missing in original at position {i}")
                break
            if i >= len(reconstructed_text):
                differences.append(f"Missing in reconstructed at position {i}")
                break
            if original_text[i] != reconstructed_text[i]:
                start = max(0, i - 10)
                end_orig = min(len(original_text), i + 10)
                end_recon = min(len(reconstructed_text), i + 10)
                differences.append(
                    f"Diff at position {i}:\n"
                    f"  Original:      {repr(original_text[start:end_orig])}\n"
                    f"  Reconstructed: {repr(reconstructed_text[start:end_recon])}"
                )
                if len(differences) >= 5:
                    differences.append(f"... and more differences")
                    break
        
        result['differences'] = differences
    
    result['success'] = is_identical
    return result


# ============================================================================
# MAIN PROGRAM
# ============================================================================

def analyze_file(filepath: str) -> None:
    """Analyze a UTF-8 text file with tree structure and generate bash script"""
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            text = file.read()
        
        print(f"\n{'='*80}")
        lexer = LexicalAnalyzer(text, os.path.basename(filepath))
        tokens = lexer.tokenize()

        parser = SyntaxAnalyzer(tokens)
        parse_tree = parser.parse()
        
        output_bash = filepath + ".sh"
        bash_script, is_valid = generate_bash_script(parse_tree, filepath)
        
        if is_valid:
            save_bash_script(bash_script, output_bash)
        else:
            print("\n⚠️  Could not generate valid bash script")
        
        if not parser.validate():
            print("\n❌ Parse failed! Please check the errors above.")
       
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
    except UnicodeDecodeError as e:
        print(f"Error: File is not valid UTF-8 - {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main program entry point"""
    if len(sys.argv) > 1:
        analyze_file(sys.argv[1])
    else:
        print("="*80)
        print("TREE STRUCTURE PARSER & BASH SCRIPT GENERATOR")
        print("="*80)
        print("\nAnalyzing tree-like directory structure and generating bash script")
        print("\n" + "-"*80)
        print("\n" + "="*80)
        print("To analyze your own tree structure file, run:")
        print("Usage: tree2bash <file>")
        print("="*80)


if __name__ == "__main__":
    main()

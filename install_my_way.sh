# For system-wide access (requires sudo)
sudo cp tree2bash.py /usr/local/bin/tree2bash
sudo chmod +x /usr/local/bin/tree2bash
# Check if installed
which tree2bash

# Basic usage
#tree2bash project_structure.txt

# Run the generated script
#bash create_project.sh

# Create a test file
#cat > test_tree.txt << 'EOF'
#myproject/
#├── src/
#│   ├── main.py
#│   └── utils/
#│       └── helpers.py
#├── tests/
#│   └── test_main.py
#└── README.md
#EOF

# Run the parser
#tree2bash test_tree.txt

# This should generate a bash script

# system-wide
#sudo rm /usr/local/bin/tree2bash

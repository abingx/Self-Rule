//2017-June-3 scripted by genBTC, original code from Symless / Synergy (Github)
#include <iostream>
#include <sstream>
#include <iomanip>

static std::string
hexEncode (std::string const& str) {
	std::ostringstream oss;
	for (size_t i = 0; i < str.size(); ++i) {
		int c = str[i];
		oss << std::setfill('0') << std::hex << std::setw(2)
			<< std::uppercase;
		oss << c;
	}
	return oss.str();
}


int main()
{
  std::string name;
  std::string userlimit;
  std::string email;
  std::string business;
  std::cout << "What is your name? ";
  getline (std::cin, name);
  std::cout << "How many userlimit max? be reasonable ";
  getline (std::cin, userlimit);
  std::cout << "What is your E-mail address? ";
  getline (std::cin, email);  
  std::cout << "What is your business/company name? ";
  getline (std::cin, business);
  std::string key;
  key="{v1;pro;" + name + ";" + userlimit + ";" + email + ";" + business + ";0;0}";
  std::cout << "The Key is this: \n";
  std::cout << hexEncode(key);
}

//    http://cpp.sh/
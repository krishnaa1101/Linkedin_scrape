# Linkedin_scrape

Script Overview

Functionality

This script automates the process of collecting key company data from LinkedIn. It performs the following steps:

1. **Login**
   Authenticates with LinkedIn using your credentials.

2. **Data Extraction**
   For each provided company LinkedIn URL, the script:

   * Extracts basic company information
   * Searches for current job postings
   * Finds contact information (phone numbers and email addresses)
   * Identifies founders and key personnel (e.g., CEO, CTO, Co-Founders)
   * Locates members of the engineering leadership team (e.g., tech leads, engineering managers)

3. **Export**
   Automatically saves all extracted data to a specified Google Sheet.

---

## **Extracted Data Fields**

| **Field**                | **Description**                                                            |
| ------------------------ | -------------------------------------------------------------------------- |
| **Company Name**         | Official name of the company                                               |
| **Description/Overview** | Brief description and business overview                                    |
| **Job Posts**            | Current job openings listed on LinkedIn                                    |
| **Number of Employees**  | Company size information as listed on LinkedIn                             |
| **Industry**             | Business sector or industry                                                |
| **Location**             | Headquarters or primary office location                                    |
| **Website**              | Official company website                                                   |
| **Domain URL**           | Domain name extracted from the website URL                                 |
| **Phone Number**         | Contact phone numbers found on LinkedIn or the company website             |
| **Email Contact**        | Contact email addresses found from public sources                          |
| **Company URL**          | LinkedIn profile URL of the company                                        |
| **Founders**             | Names and LinkedIn profiles of CEO, CTO, and Co-Founders                   |
| **Engineering Heads**    | Names and LinkedIn profiles of engineering managers, tech leads, directors |

---

Let me know if you'd like a version tailored for technical documentation, marketing, or internal use!

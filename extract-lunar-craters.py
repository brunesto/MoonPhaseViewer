import requests
from bs4 import BeautifulSoup
import json
import re
import requests_cache


def parse_coordinates(coords_str):
    """
    Converts a coordinates string (e.g., '8.42°S') to a pair of decimal values
    """
      
    coords_str=coords_str.replace('\ufeff',' ')
   
    # coords from wikipedia are often in pair decimal / degree format
    coords_str=coords_str.split('/',1)[0]

    latSepIdx=max(coords_str.find('N'), coords_str.find('S'))
    lonSepIdx=max(coords_str.find('W'), coords_str.find('E'))

    if latSepIdx == -1 or lonSepIdx == -1 or latSepIdx >= lonSepIdx:
        print(f"Skipping row with invalid coordinates: {coords_str}")
        return None,None
    
    lat_str = coords_str[:latSepIdx + 1].strip()
    lon_str = coords_str[latSepIdx+1:lonSepIdx + 1].strip()
    
    lat=parse_coordinate(lat_str)
    lon=parse_coordinate(lon_str)
    if lat is None or lon is None:
        print(f"Skipping row with invalid coordinates: {coords_str}")
        return None,None
    return (lat,lon)    

def parse_coordinate(coord_str):
    """
    Converts a coordinate string (e.g., '82° 3'' S') to a decimal value.
    S and W directions are converted to negative values.

    """
        
    # print(f"Parsing coordinate: {coord_str}")
    # # https://stackoverflow.com/questions/33997361/how-to-convert-degree-minute-second-to-degree-decimal
    
    deg=0
    minutes=0
    seconds=0
    direction=None
    
    # Replace special characters with standard ones
    coord_str=coord_str.replace("′","'");
    coord_str=coord_str.replace("″","''")

    if coord_str.find("'")!=-1:
        if coord_str.find("''")!=-1:
            deg, minutes, seconds,direction=  re.split('[°\'"]', coord_str)
        else:
            deg, minutes,direction=  re.split('[°\'"]', coord_str)
    else:
         deg,direction=  re.split('[°\'"]', coord_str)

    decimal_value=(float(deg) + float(minutes)/60 + float(seconds)/(60*60)) 
    if direction in ['W', 'S']:
        decimal_value *= -1
    # print(f"Parsing coordinate: {coord_str} decimal_value: {decimal_value}")       
    return decimal_value


def get_crater_links(url):
    """
    Gets the links to the alphabetical sub-pages of lunar craters.

    Args:
        url (str): The URL of the main Wikipedia page for the list of craters.

    Returns:
        list: A list of URLs for the sub-pages.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.content, "html.parser")

        # Find the links to the alphabetical sub-pages
        links = []
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("/wiki/List_of_craters_on_the_Moon:"):
                ref= a["href"]
                if ref.find("#")!=-1:
                    ref=ref.rpartition("#")[0]
                links.append("https://en.wikipedia.org" + ref)

        # Remove duplicate links
        return sorted(list(set(links)))

    except requests.exceptions.RequestException as e:
        print(f"Error fetching the main page: {e}")
        return []


def scrape_crater_data(url):
    """
    Scrapes crater data from a given Wikipedia page.

    Args:
        url (str): The URL of the page to scrape.

    Returns:
        list: A list of dictionaries, where each dictionary represents a crater.
    """
    craters = []
    try:
        print(f"Scraping data from: {url}")
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Find all tables with the wikitable class
        tables = soup.find_all("table", class_="wikitable")

        for table in tables:
            # The header row is usually the first row
            headers = [header.get_text(strip=True) for header in table.find_all("th")]

            # Find the indices for 'Crater' and 'Diameter'
            try:
                name_index = headers.index("Crater")
                diameter_index = headers.index("Diameter(km)")
                coordinates_index = headers.index("Coordinates")
                

            except ValueError:
                # If headers are not found, skip this table
                continue

            for row in table.find_all("tr")[1:]:  # Skip header row
                cells = row.find_all("td")
                if len(cells) > max(name_index, diameter_index):
                    name = cells[name_index].get_text(strip=True)
                   
                    diameter_text = cells[diameter_index].get_text(strip=True)

                    coordinates_text = cells[coordinates_index].get_text(strip=True).upper()
                    lat,lon=parse_coordinates(coordinates_text)
                    if lat is None or lon is None:
                        continue

                    if (lon>90 or lon<-90):
                        print(name+" is on far side")
                        continue
                        
                    diameter = float(diameter_text)

                    craters.append({"name": name, "diameter": diameter ,"lat": lat,"lon": lon})
        

    except requests.exceptions.RequestException as e:
        print(f"Error scraping {url}: {e}")

    return craters


def main():
    """
    Main function to orchestrate the scraping, filtering, and saving of crater data.
    """
    main_url = "https://en.wikipedia.org/wiki/List_of_craters_on_the_Moon"


    requests_cache.install_cache()

    print("Fetching links to sub-pages...")
    sub_page_links = get_crater_links(main_url)

    if not sub_page_links:
        print("No sub-pages found. Exiting.")
        return

    all_craters = []
    for link in sub_page_links:
        print(f"Scraping data from: {link}")
        all_craters.extend(scrape_crater_data(link))

    print(f"\nFound a total of {len(all_craters)} craters.")


    dump_craters(all_craters, "large",300,99999 )
    dump_craters(all_craters, "medium",150,300 )
    dump_craters(all_craters, "small",50,150 )
    dump_craters(all_craters, "tiny",10,50 )
    
    
def dump_craters(all_craters,suffix,min_diameter, max_diameter):

    # Filter craters with diameter > 100 km
    large_craters = [
        crater for crater in all_craters if crater.get("diameter", 0) >= min_diameter and crater.get("diameter", 0) < max_diameter
    ]
    print(f"Found {len(large_craters)} craters with a diameter [{min_diameter},{max_diameter}] km.")

    # Export the filtered list to a JSON file
    output_filename = f"craters_{suffix}.js"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(f"//list of {len(large_craters)} near side craters with diameter [{min_diameter},{max_diameter}] km\n")
        f.write(f"//extracted from wikipedia. Text is available under the Creative Commons Attribution-ShareAlike 4.0 License; additional terms may apply. \n")
        f.write(f"craters_{suffix}=")
        json.dump(large_craters, f, ensure_ascii=False, indent=4)
        f.write("\n")
    print(f"\nSuccessfully exported the list of large craters to {output_filename}")


if __name__ == "__main__":
    main()

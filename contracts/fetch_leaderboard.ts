import axios from 'axios';

interface Entry {
  score: string;
  contestant: string;
}

const cycle = "1"; // Set the cycle value programmatically

const query = `
  query {
    newEntries(where: { cycle: "${cycle}" }, orderBy: blockTimestamp, orderDirection: asc) {
      score
      contestant
    }
  }
`;

axios
  .post('https://api.thegraph.com/subgraphs/name/ethan-crypto/crypto_idol', {
    query: query,
  })
  .then((response) => {
    let newEntries = response.data.data.newEntries;
    console.log(newEntries);
    let uniqueEntriesMap: { [key: string]: Entry } = {};
    newEntries.forEach((entry: Entry) => {
      const contestant = entry.contestant;
      uniqueEntriesMap[contestant] = entry;
    }); 
    console.log(uniqueEntriesMap);
    // Step 3
    const leaderboard: Entry[] = Object.values(uniqueEntriesMap);
    
    // Step 4
    leaderboard.sort((a, b) => Number(b.score) - Number(a.score));
    
    console.log(leaderboard);
  })
  .catch((error) => {
    console.error(error);
  });

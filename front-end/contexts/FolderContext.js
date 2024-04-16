import React, {createContext, useContext, useState} from 'react';

const FolderContext = createContext();

export const FolderProvider = ({children}) =>{
    const [folderID,setFolderID] = useState(-1);


    return(
        <FolderContext.Provider value={{folderID, setFolderID}}>
            {children}
        </FolderContext.Provider>
    );

};

export const useFolder = () => useContext(FolderContext)
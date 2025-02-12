import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemText,
  Button,
  TextField,
  Divider,
} from '@mui/material';

interface ChapterBreakdownProps {
  outline: string;
  onBreakdownComplete: (breakdown: any[]) => void;
}

interface Chapter {
  title: string;
  content: string;
  sections: string[];
  references: string[];
  wordCount: number;
}

const ChapterBreakdown: React.FC<ChapterBreakdownProps> = ({
  outline,
  onBreakdownComplete,
}) => {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Parse the outline into chapters
    const parseOutline = () => {
      try {
        // Split the outline into lines and process them
        const lines = outline.split('\n').filter(line => line.trim());
        const parsedChapters: Chapter[] = [];
        let currentChapter: Partial<Chapter> = {};
        let currentSections: string[] = [];
        let currentReferences: string[] = [];
        let isInReferences = false;

        lines.forEach(line => {
          // Match chapter title with word count
          const chapterMatch = line.match(/^Chapter \d+:.*?\(Word Count: (\d+)\)/i) || 
                             line.match(/^\d+\..*?\(Word Count: (\d+)\)/);
          
          if (chapterMatch) {
            if (currentChapter.title) {
              parsedChapters.push({
                ...currentChapter,
                sections: currentSections,
                references: currentReferences,
                wordCount: currentChapter.wordCount || 3500,
              } as Chapter);
            }
            const wordCount = parseInt(chapterMatch[1]) || 3500;
            currentChapter = {
              title: line.replace(/\(Word Count: \d+\)/i, '').trim(),
              content: '',
              wordCount: wordCount,
            };
            currentSections = [];
            currentReferences = [];
            isInReferences = false;
          } else if (line.toLowerCase().includes('key references:')) {
            isInReferences = true;
          } else if (line.match(/^\s*-/)) {
            if (isInReferences) {
              currentReferences.push(line.trim().replace(/^-\s*/, ''));
            } else {
              currentSections.push(line.trim().replace(/^-\s*/, ''));
            }
          } else if (currentChapter.title) {
            if (!line.toLowerCase().includes('sections:')) {
              currentChapter.content = (currentChapter.content || '') + ' ' + line.trim();
            }
          }
        });

        // Add the last chapter
        if (currentChapter.title) {
          parsedChapters.push({
            ...currentChapter,
            sections: currentSections,
            references: currentReferences,
            wordCount: currentChapter.wordCount || 3500,
          } as Chapter);
        }

        console.log('Parsed chapters:', parsedChapters); // Debug log
        setChapters(parsedChapters);
      } catch (err) {
        setError('Error parsing outline');
        console.error('Error parsing outline:', err);
      }
    };

    if (outline) {
      parseOutline();
    }
  }, [outline]);

  const handleWordCountChange = (index: number, value: string) => {
    const newWordCount = parseInt(value) || chapters[index].wordCount;
    const updatedChapters = [...chapters];
    updatedChapters[index] = {
      ...updatedChapters[index],
      wordCount: newWordCount,
    };
    setChapters(updatedChapters);
  };

  const handleComplete = () => {
    onBreakdownComplete(chapters);
  };

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="h6" gutterBottom>
        Review Chapter Breakdown
      </Typography>
      
      {error && (
        <Typography color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}

      <List>
        {chapters.map((chapter, index) => (
          <Paper key={index} sx={{ mb: 2, p: 2 }}>
            <Typography variant="h6">{chapter.title}</Typography>
            <Typography variant="body2" sx={{ mt: 1, mb: 1 }}>
              {chapter.content}
            </Typography>
            
            <Typography variant="subtitle2" sx={{ mt: 2 }}>
              Sections:
            </Typography>
            <List dense>
              {chapter.sections.map((section, sIndex) => (
                <ListItem key={sIndex}>
                  <ListItemText primary={section} />
                </ListItem>
              ))}
            </List>

            {chapter.references && chapter.references.length > 0 && (
              <>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2">
                  Key References:
                </Typography>
                <List dense>
                  {chapter.references.map((reference, rIndex) => (
                    <ListItem key={rIndex}>
                      <ListItemText 
                        primary={reference}
                        sx={{ '& .MuiListItemText-primary': { fontStyle: 'italic' } }}
                      />
                    </ListItem>
                  ))}
                </List>
              </>
            )}

            <TextField
              label="Word Count"
              type="number"
              value={chapter.wordCount || ''}
              onChange={(e) => handleWordCountChange(index, e.target.value)}
              sx={{ mt: 2 }}
              size="small"
              helperText={`Approximately ${Math.round((chapter.wordCount || 0) / 900)} pages`}
            />
          </Paper>
        ))}
      </List>

      <Button
        variant="contained"
        color="primary"
        onClick={handleComplete}
        sx={{ mt: 2 }}
      >
        Confirm Breakdown
      </Button>
    </Box>
  );
};

export default ChapterBreakdown; 
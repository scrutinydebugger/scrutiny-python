/**
 *  Some homemade templated collections.
 *
 * @author Pier-Yves Lessard
 * */


#ifndef ___LIB_COLLECTION_H___
#define ___LIB_COLLECTION_H___       

#include "scrutiny_setup.h"
#include "cstring"


#ifndef MIN
#define MIN(x,y) ((x<y) ? (x) : (y))
#endif

#ifndef MAX
#define MAX(x,y) ((x>y) ? (x) : (y))
#endif


namespace scrutiny
{

    typedef enum {
        FIFO,
        STACK
    } CollectionType;

    template <typename  T, unsigned short SIZE,  CollectionType TYPE, bool ATOMIC=false >
    class Collection 
    {
    public:
        
        typedef union Error 
        {
            struct 
            {
                bool underrun:1;
                bool overrun:1; 
                bool reserved:6;
            };
            bool all;
        } CollectionError_t;

        Collection();
        bool push(const T* element);
        bool push(const T* src, unsigned short n);
        bool pop(T* element); 
        bool pop(T* dst, unsigned short n);
        void clear(); 

        inline unsigned short count()
        {
            return _nbItem;
        }

        inline unsigned short size()
        {
            return SIZE;
        }

        inline bool empty()
        {
            return (_nbItem==0);
        }

        inline bool full()
        {
            return (_nbItem>=SIZE);
        }

        inline bool underrun()
        {
            return _error.underrun;
        }

        inline bool overrun()
        {
            return _error.overrun;
        }

        inline bool error()
        {
            return (_error.all!=0); 
        }

        unsigned short _head ;
        unsigned short _tail ;
        volatile unsigned short _nbItem ;    // Volatile because of full/empty/count function
        volatile CollectionError_t _error ;  // volatile because of underrun/overrun/error function
        T _data[SIZE];

    };


    template <typename  T, unsigned short SIZE, CollectionType TYPE, bool ATOMIC>
    Collection<T,SIZE,TYPE,ATOMIC>::Collection() : 
        _head(0),
        _tail(0),
        _nbItem(0),
        _error{false, false},
        _data{}
    {

    }


    template <typename  T, unsigned short SIZE, CollectionType TYPE, bool ATOMIC>
    bool Collection<T,SIZE,TYPE,ATOMIC>::push(const T* element)
    {
        AtomicContext context;
        bool success = true;

        if (ATOMIC)
            make_atomic(&context);
        
        if (full())
        {
            _error.overrun=true;
            success = false;
        }
        else
        {
            _data[_head] = *element;

            _head++;
            if (_head >= SIZE)
                _head=0;

            _nbItem++;
        }

        if (ATOMIC)
            undo_atomic(&context);
        
        return success;
    }


    template <typename  T, unsigned short SIZE, CollectionType TYPE, bool ATOMIC>
    bool Collection<T,SIZE,TYPE,ATOMIC>::pop(T* element)
    {
        AtomicContext context;
        bool success = true;
        if (ATOMIC)
            make_atomic(&context);
        
        if (empty())
        {
            _error.underrun = true;
            success = false;
        }
        else
        {
            if (TYPE == FIFO)
            {
                *element = _data[_tail];
                
                _tail++;
                if (_tail >= SIZE)
                    _tail=0;
            }
            else if (TYPE == STACK)
            {
                if (_head ==0)
                    _head=SIZE-1;
                else
                    _head--;

                *element = _data[_head];
            }
            _nbItem--;
        }

        if (ATOMIC)
            undo_atomic(&context);
        
        return success;
    }

    /**
     * Reset the Collection by deleting its content and clearing errors.
     */
    template <typename  T, unsigned short SIZE, CollectionType TYPE, bool ATOMIC>
    void Collection<T,SIZE,TYPE,ATOMIC>::clear()
    {
        AtomicContext context;
        if (ATOMIC)
            make_atomic(&context);
        
        _nbItem = 0;
        _head=0;
        _tail=0;
        _error.overrun=false;
        _error.underrun=false;

        if (ATOMIC)
            undo_atomic(&context);
    }

    /**
     * Copy the ordered content of the Collection into an external buffer.
     */
    template <typename  T, unsigned short SIZE, CollectionType TYPE, bool ATOMIC>
    bool Collection<T,SIZE,TYPE,ATOMIC>::pop(T* dst, unsigned short n)
    {
        AtomicContext context;
        unsigned short mid;
        unsigned short i=0;
        unsigned short j;
        bool success = true;

        if (ATOMIC)
            make_atomic(&context);

        if (n>_nbItem)
        {
            n=_nbItem;
            _error.underrun=true;
            success=false;
        }

        if (TYPE == FIFO)
        {
            mid = MIN(SIZE-_tail, n);
            j=mid;

            while(j--)
                dst[i++] = _data[_tail++];

            if (_tail>=SIZE)
            {
                _tail=0;
                j=n-mid;
                i=mid;
                while(j--)
                    dst[i++]=_data[_tail++];
            }
        }
        else if (TYPE == STACK)
        {
            if (_head>_tail)
            {
                j = n;  // Size checked above.
                while(j--)
                    dst[i++]=_data[--_head];
            }
            else
            {
                mid = MIN(_head, n);
                j=mid;
                while(j--)
                    dst[i++]=_data[--_head];
                _head=SIZE;
                i = 0;
                j = n-mid;
                while(j--)
                    dst[i++] = _data[--_head];
            }
        }

        _nbItem -= n;

        if (ATOMIC)
            undo_atomic(&context);

        return success;
    }

    /**
     * Copy the content of an external buffer into the collection.
     */
    template <typename  T, unsigned short SIZE, CollectionType TYPE, bool ATOMIC>
    bool Collection<T,SIZE,TYPE,ATOMIC>::push(const T* src, unsigned short n)
    {
        AtomicContext context;
        unsigned short mid;
        unsigned short i=0;
        unsigned short j;
        bool success = true;

        if (ATOMIC)
            make_atomic(&context);

        if (n>SIZE-_nbItem)
        {
            _error.overrun = true;
            n = SIZE-_nbItem;
            success=false;
        }

        mid = MIN(SIZE-_head, n);
        j=mid;
        while(j--)
            _data[_head++] = src[i++];

        if (_head >= SIZE)
            _head=0;

        j=n-mid;
        while(j--)
            _data[_head++] = src[i++];

        _nbItem += n;

        if (ATOMIC)
            undo_atomic(&context);

        return success;
    }

    template<typename T, unsigned short SIZE>
    using Fifo=Collection<T, SIZE, FIFO> ;

    template<typename T, unsigned short SIZE>
    using AtomicFifo=Collection<T, SIZE, FIFO, true> ;

    template<typename T, unsigned short SIZE>
    using Stack=Collection<T, SIZE, STACK> ;

    template<typename T, unsigned short SIZE>
    using AtomicStack=Collection<T, SIZE, STACK, true> ;
    }

#endif